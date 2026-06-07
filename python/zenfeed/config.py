import json
import os
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel

_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

class LLMType(Enum):
    Embed = "embed"
    General = "general"

class RewriteType(Enum):
    ToText = "transform.to_text"

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

# TODO: 实现Watch的结构选型
class Watch(BaseModel):
    name: str
    receiver: str
    query_arg: FilterQuery | None
    vec_query_arg: VectorQuery | None

class LLMProvider(BaseModel):
    api_base: str
    api_key: str

class RewriteRule(BaseModel):
    name: str
    type: RewriteType
    llm: str
    prompt_t: str
    label: str

class LLM(BaseModel):
    name: str
    model_id: str
    type: LLMType
    max_concurrency: int
    provider: LLMProvider

class Config(BaseModel):
    scraper_config: Scraper
    llm_config: list[LLM]
    rewrite_rules: list[RewriteRule]
    scheduler_rules: list[Periodic]
    channels_config: ChannelsConfig
    receiver_config: list[ReceiverConfig]
    
    def find_llm(self, name: str) -> LLM | None :
        for llm in self.llm_config:
            if llm.name == name:
                return llm
        return None


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
