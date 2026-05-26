# PRIMARY_DESIGN.md

原始项目 zenfeed（`/Users/a12345/Desktop/code/zenfeed`）的核心设计文档，供本项目开发时参考，避免反复回原始仓库阅读代码。

## 项目定位

zenfeed 是一个 AI 驱动的 RSS 信息中枢。抓取 RSS 源 → LLM 管道处理（摘要、分类、打分、过滤）→ 带向量嵌入的存储 → 定时规则查询 → 通知推送。

## 数据模型

核心数据结构是 `model.Feed`，由一组排序的 key-value 标签（`Labels`）加一个时间戳组成。设计灵感来自 Prometheus 的 relabeling 机制。

```
Feed {
    ID:     uint64
    Labels: [{Key: "title", Value: "..."}, {Key: "content", Value: "..."}, ...]
    Time:   timestamp
}
```

内置标签键：`type`, `source`, `title`, `link`, `pub_time`, `content`。rewrite 管道可以添加任意自定义标签（如 `summary`, `score`, `category`）。

Labels 始终按 Key 字典序排列，支持 `Get`, `Put`, `FromMap`, `Map` 操作。JSON 序列化为扁平对象 `{"key1": "val1", "key2": "val2"}`。

标签过滤器支持 `=`（等于）和 `!=`（不等于）两种操作。

## 组件系统

### Component 接口

所有业务子系统实现 `component.Component` 接口：

```
Component {
    Name() string       // 组件类型名，如 "FeedStorage"
    Instance() string   // 实例名，如 "Global"
    Run() error         // 阻塞运行直到关闭
    Ready() <-chan      // 返回就绪通知 channel
    Close() error       // 关闭组件
}
```

### Base 嵌入

具体组件嵌入 `component.Base[Config, Dependencies]`，它提供：
- 上下文管理（ctx/cancel）
- 就绪通知（MarkReady/Ready channel）
- 配置读写（Config()/SetConfig()，带读写锁）
- 遥测标签（组件名 + 实例名 + 自定义标签）

### Factory 模式

每个包导出 `NewFactory()`，返回 `component.Factory`。构造签名统一为：

```
Factory.New(instance string, config *Config, dependencies Dependencies) (Component, error)
```

其中 `Dependencies` 结构体显式声明该组件依赖的其他组件。

### 启动编排

`main.go` 中通过 `component.Run(ctx, groups...)` 编排启动顺序：
- Groups 之间顺序启动（前一个 group 所有组件 Ready 后才启动下一个）
- Group 内部并发启动
- 关闭顺序相反（后启动的先关闭）

实际启动顺序：
1. ConfigManager
2. LLMFactory, ObjectStorage, Telemetry
3. Rewriter
4. FeedStorage
5. KVStorage
6. Notifier, API
7. HTTP, MCP, RSS, ScraperManager, Scheduler

### 配置热重载

`config.Manager` 监听 `config.yaml` 文件变更，通过 `config.Watcher` 接口通知订阅者。大部分组件同时实现 `Component` 和 `Watcher`。`Watcher` 的 `OnConfigChange(newConf *config.App) error` 回调在配置变更时触发。

## 数据管道

```
RSS Sources → Scrape Manager → Rewrite Pipeline → Feed Storage
                                                       ↓
                                    Scheduler (periodic/watch rules) → Notify Channel
```

### Scrape（抓取）

- `scrape.Manager` 管理多个 `scraper.Scraper`
- 每个 Scraper 对应一个 RSS 源，按配置间隔（默认 1h）轮询
- 支持 RSSHub 路由路径（通过 RSSHub endpoint 代理）
- 抓取时间窗口 `past`（默认 3d）过滤过旧条目
- 抓取到的内容构建为 `model.Feed`，写入 FeedStorage
- 通过 KVStorage 记录已抓取 ID，避免重复

### Rewrite（重写管道）

设计灵感来自 Prometheus relabeling。Feed 写入存储前，经过一系列 rewrite 规则：

规则类型：
- **filter**: 根据标签值过滤（正则匹配），不匹配则丢弃整条 feed
- **replace**: 正则替换标签值
- **set**: 直接设置标签值
- **transform.to_text**: 用 LLM 处理标签，生成新的文本标签（如摘要、分类、打分）
- **transform.to_audio**: 用 LLM TTS 生成音频
- **crawl**: 抓取 URL 对应的网页正文

LLM transform 的 prompt 中可以用 Go template 语法引用其他标签值，如 `{{ .content }}`。

### Feed Storage（存储引擎）

这是整个项目最复杂的部分，类 TSDB（时序数据库）设计。

#### 分层结构

```
Feed Storage
  └── Block[] (时间分块，默认 25h 一个)
        ├── Chunk (列式数据存储)
        ├── Primary Index (ID → 位置映射)
        ├── Inverted Index (标签值 → ID 列表)
        └── Vector Index (向量相似度搜索)
```

#### Block（数据块）

- 每个 Block 覆盖一个时间范围 `[start, end)`
- 状态机：Hot（可写，索引在内存）→ Cold（只读，索引在磁盘）
- `TransformToCold()` 将热块冻结为冷块，flush 到磁盘
- 过期 Block 由 retention 机制删除（默认 8 天）

#### Chunk（数据块内的列式存储）

- 每个标签键一个 chunk 文件
- 字典编码：先建字典（去重字符串），再用字典 ID 索引
- 支持 mmap 读取，减少内存拷贝
- 编码格式：`[字典区][偏移区][ID引用区]`

#### Primary Index

- Feed ID → chunk 内行号的映射
- 用于按 ID 精确查找

#### Inverted Index（倒排索引）

- 标签值 → Feed ID 列表（posting list）
- 用于按标签过滤，如 `source=hackernews`
- 支持等于/不等于过滤

#### Vector Index（向量索引）

- Feed 的标签文本经 LLM Embedding 后存储为向量
- 支持余弦相似度搜索
- 用于语义查询，如"最近关于 AI 的文章"
- 查询时先将查询文本 embedding，再与存储向量计算相似度
- 返回相似度得分（score），用于排序

#### 查询流程

QueryOptions 包含：
- `Query`: 语义搜索文本（可选）
- `LabelFilters`: 标签过滤条件
- `Start/End`: 时间范围
- `Limit`: 返回数量限制

查询在所有符合时间范围的 Block 上并行执行，结果合并排序。

### Schedule（调度）

两种规则类型：

- **Periodic**: 定时执行查询（如每天 8:00），结果打包发送
- **Watch**: 持续监控，当查询结果满足条件时触发（如相似度超过阈值）

规则查询 FeedStorage，结果通过 channel 传递给 Notifier。

### Notify（通知）

- **Route**: 树形路由结构，根据标签匹配将结果分发到不同 Receiver
- **Receiver**: 通知接收者配置（聚合策略、目标 channel）
- **Channel**: 实际发送通道
  - Email: SMTP 发送，支持 HTML 模板
  - Webhook: HTTP POST，支持自定义 payload 模板

## API 层

- **HTTP API** (`:1300`): RESTful 接口，查询 feed、管理配置、代理 RSSHub
- **MCP Server** (`:1301`): Model Context Protocol 服务，供 AI 客户端接入
- **RSS Server** (`:1302`): 将存储的 feed 重新导出为 RSS 格式

API 层依赖 `api.API` 接口，三种传输协议共享同一套业务逻辑。

## LLM 集成

`llm.Factory` 管理多个 LLM 实例，按名称引用。支持的能力：
- `String()`: 文本生成（摘要、分类等）
- `Embedding()` / `EmbeddingLabels()`: 向量嵌入
- `WAV()`: TTS 音频生成

支持的 Provider（均兼容 OpenAI API 格式）：
- openai, openrouter, deepseek, gemini, volc, siliconflow

Embedding 结果有缓存机制（通过 KVStorage），避免重复计算。

## 配置结构

单个 `config.yaml` 文件，顶层结构：

```yaml
timezone: Asia/Shanghai
telemetry:
  address: ":9090"
  log:
    level: info
llms:                    # LLM 实例列表
  - name: general
    provider: siliconflow
    model: Qwen/Qwen3-8B
    api_key: sk-xxx
  - name: embed
    provider: siliconflow
    embedding_model: Qwen/Qwen3-Embedding-4B
    api_key: sk-xxx
scrape:                  # 抓取配置
  rsshub_endpoint: http://rsshub:1200
  interval: 1h
  past: 3d
  sources: [...]
storage:
  feed:
    rewrites: [...]      # rewrite 管道规则
    embedding_llm: embed
    retention: 8d
    block_duration: 25h
scheduls:                # 调度规则
  rules: [...]
notify:                  # 通知配置
  route: {...}
  receivers: [...]
  channels:
    email: {...}
```

## 遥测

- 结构化日志：基于 `slog`，通过 `telemetry/log` 包装，自动注入组件标签
- Prometheus 指标：通过 `promauto` 注册，按组件/实例维度分组
- 遥测服务器：`:9090` 暴露 `/metrics` 端点

## 关键设计决策

1. **标签模型而非固定 schema**: Feed 是灵活的 key-value 集合，新增字段不需要改存储结构
2. **管道式处理**: Rewrite 规则可以自由组合，每个规则只做一件事，通过管道串联
3. **时间分块存储**: 类 Prometheus TSDB，按时间范围分块管理，简化 retention 和查询
4. **显式依赖注入**: Dependencies 结构体让组件间依赖关系一目了然，无隐式全局状态
5. **配置热重载**: 大部分配置变更不需要重启服务
