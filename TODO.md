# TODO

## Misc

- [ ] **配置模型与校验收口**：补齐 Watch 规则的数据结构，并把邮件收件人列表、Receiver 绑定 Channel 等配置一致性检查前移到加载阶段
- [ ] **Rewrite 路由与错误处理**：整理规则类型到处理函数的映射方式；当配置引用了不存在的 LLM 时，改为明确失败或记录日志
- [ ] **LLM 调用消息规范**：统一模型调用的消息构造入口，补充系统提示词，避免每条规则只裸传用户 prompt

## Scraper 优化

- [x] **按 link 去重**：同一 RSS 源内和跨源都去重，避免重复抓取同一篇文章
- [ ] **Etag / Last-Modified 缓存**：利用 HTTP 条件请求，避免反复抓取未变更内容
- [x] **异步抓取**：用 asyncio + aiohttp 并发抓取多个 RSS 源，减少总等待时间

## 核心模块

- [ ] **调度器 (Scheduler)**
  - [x] Periodic 规则：定时执行查询（如每天 8:00），结果打包发送
  - [ ] Watch 规则：持续监控，当查询结果满足条件时触发通知
- [x] **通知系统 (Notifier)**
  - Route 路由：按标签匹配分发到不同 Receiver
  - Receiver：聚合策略 + 目标 Channel
  - Channel 实现：Email（SMTP）、Webhook（HTTP POST）

## Rewrite 扩展

- [ ] **filter 规则**：根据标签值正则匹配，不匹配则丢弃整条 feed
- [ ] **replace 规则**：正则替换标签值
- [ ] **set 规则**：直接设置标签值
- [ ] **crawl 规则**：抓取 URL 对应的网页正文

## LLM 扩展

- [x] **Embedding**：文本向量化，为语义搜索提供支持
- [x] **TTS**：文本转语音（transform.to_audio）
- [x] **Embedding 缓存**：通过 KVStorage 避免重复计算

## 基础设施

- [ ] **CLI 入口**：命令行参数解析（配置文件路径、子命令等）
- [ ] **KVStorage**：键值存储，用于去重标记、Embedding 缓存等
- [ ] **Rust 侧配置桥接**：WINDOW、存储路径等从配置文件传入 Rust
