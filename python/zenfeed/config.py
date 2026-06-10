import json
import logging
import os
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, model_validator

_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

logger = logging.getLogger(__name__)

class LLMType(Enum):
    Embed = "embed"
    General = "general"
    Tts = "tts"

class RewriteType(Enum):
    ToText = "transform.to_text"
    Filter = "filter"           # audit:rewrite-types
    Replace = "replace"         # audit:rewrite-types
    Set = "set"                 # audit:rewrite-types
    Crawl = "crawl"             # audit:rewrite-types

class RSS(BaseModel):
    name: str
    url: str

class ContentTemplate(BaseModel):
    item_template: str
    separator: str

class EmailContent(BaseModel):
    # content的模版类
    subject: str
    content: ContentTemplate        

class EmailChannel(BaseModel):
    name: str
    url: str
    port: int
    user: str
    passwd: str
    mail_meta: list[str]        # 规定列表的第一个地址是发件人地址
    mail_content_t: EmailContent  # 依旧是采用配置模版的形式

class WebhookChannel(BaseModel):
    name: str
    url: str
    http_method: str = "POST"
    body_template: ContentTemplate

class ChannelsConfig(BaseModel):
    smtp: list[EmailChannel]
    webhook: list[WebhookChannel]

class ReceiverConfig(BaseModel):
    name: str
    channel: str                # 定义这个receiver要持有哪一个名字对应的channel实例
    slice_size: int             # 配置每次发邮件的最大feed数量

class FilterQuery(BaseModel):
    filter: tuple[str, list[str] | None] | None
    s2e: tuple[int | None, int | None]
    mode: bool
    limit: int | None

class VectorQuery(BaseModel):
    vector: list[float]
    s2e: tuple[int | None, int | None]
    limit: int | None

class Scraper(BaseModel):
    interval: int
    rss_list: list[RSS]

class Periodic(BaseModel):
    name: str
    cron: str
    receiver: str
    filt_query_arg: FilterQuery | None
    vec_query_arg: VectorQuery | None

class Watch(BaseModel):
    name: str
    interval: int = 60           # audit:watch-config 检查间隔(秒)
    receiver: str
    filt_query_arg: FilterQuery | None
    vec_query_arg: VectorQuery | None

class LLMProvider(BaseModel):
    api_base: str
    api_key: str

class RewriteRule(BaseModel):
    name: str
    type: RewriteType
    llm: str | None = None          # audit:rewrite-rule-opt 非transform规则不需要LLM
    prompt_t: str | None = None     # audit:rewrite-rule-opt 模版字符串/正则pattern
    label: str | None = None        # audit:rewrite-rule-opt 目标标签
    system_prompt_t: str | None = None  # audit:llm-system 系统提示词语模版
    replacement: str | None = None  # audit:rewrite-rule-opt replace规则的替换字符串
    value: str | None = None        # audit:rewrite-rule-opt set规则的固定值
    url_label: str | None = None    # audit:rewrite-rule-opt crawl规则指示哪个标签包含URL

class LLM(BaseModel):
    name: str
    model_id: str
    type: LLMType
    max_concurrency: int
    provider: LLMProvider

class Storage(BaseModel):            # audit:storage-config
    window: int = 90000
    data_dir: str = ".zenfeed"

class Config(BaseModel):
    scraper_config: Scraper
    llms_config: list[LLM]
    rewrite_rules: list[RewriteRule]
    scheduler_rules: list[Periodic] = []
    watch_rules: list[Watch] = []   # audit:watch-config
    channels_config: ChannelsConfig
    receiver_config: list[ReceiverConfig]
    storage_config: Storage = Storage()  # audit:storage-config

    @model_validator(mode="after")    # audit:config-validate
    def _validate_consistency(self) -> "Config":
        llm_names = {llm.name for llm in self.llms_config}
        channel_names = {c.name for c in self.channels_config.smtp} | {c.name for c in self.channels_config.webhook}
        receiver_names = {r.name for r in self.receiver_config}

        for rule in self.rewrite_rules:
            if rule.llm is not None and rule.llm not in llm_names:
                logger.warning("rewrite rule %r references unknown LLM %r", rule.name, rule.llm)

        for r in self.receiver_config:
            if r.channel not in channel_names:
                logger.warning("receiver %r references unknown channel %r", r.name, r.channel)

        for rule in self.scheduler_rules:
            if rule.receiver not in receiver_names:
                logger.warning("periodic rule %r references unknown receiver %r", rule.name, rule.receiver)

        for rule in self.watch_rules:  # audit:watch-config
            if rule.receiver not in receiver_names:
                logger.warning("watch rule %r references unknown receiver %r", rule.name, rule.receiver)

        for ch in self.channels_config.smtp:
            if len(ch.mail_meta) < 1:
                logger.warning("email channel %r has empty mail_meta", ch.name)

        return self


def _resolve_env_placeholders(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _resolve_env_placeholders(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_resolve_env_placeholders(item) for item in value]

    if isinstance(value, str):
        def replace_env_var(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in os.environ:
                raise ValueError(f"Missing environment variable: {name}")
            return os.environ[name]

        return _ENV_VAR_PATTERN.sub(replace_env_var, value)

    return value


def load(CONFIG_FILE_PATH: str) -> Config :
    with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
        raw_config = json.load(f)
    return Config.model_validate(_resolve_env_placeholders(raw_config))
