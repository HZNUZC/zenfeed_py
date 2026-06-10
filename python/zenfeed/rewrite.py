import logging
import re
import aiohttp
from zenfeed import config, llm
from .zenfeed import Feed, Labels

logger = logging.getLogger(__name__)

_KEEP = object()  # audit:rewrite-filter 哨兵值：保留feed但不写入标签

class RewritePipe:
    
    def __init__(self, rules: list[config.RewriteRule], name2llm: llm.LLMs):
        self.rules = rules
        self.llms = name2llm
        # audit:rewrite-route dict映射替代if-elif链
        self._handlers: dict = {  # type: ignore[type-arg]
            config.RewriteType.ToText: self._to_text,
            config.RewriteType.Filter: self._filter,
            config.RewriteType.Replace: self._replace,
            config.RewriteType.Set: self._set,
            config.RewriteType.Crawl: self._crawl,
        }

    async def rewrite(self, feed: Feed) -> Feed | None:

        labels = feed.get_labels().map()

        if labels is None:
            return None

        for rule in self.rules:
            handler = self._handlers.get(rule.type)
            if handler is None:
                logger.warning("unknown rewrite rule type %r", rule.type)
                continue

            # audit:rewrite-error 明确日志而不是静默忽略
            if rule.type in (config.RewriteType.ToText,) and rule.llm and self.llms.get(rule.llm) is None:
                logger.warning("rewrite rule %r: LLM %r not found, skipping", rule.name, rule.llm)
                continue

            result = await handler(rule, labels)  # type: ignore[arg-type]  # audit:rewrite-route

            if result is None:
                return None  # audit:rewrite-filter filter不匹配时丢弃整条feed

            if isinstance(result, str) and rule.label:  # type: ignore[arg-type]
                labels[rule.label] = result

            # 回写Feed
            feed.set_labels(Labels.from_map(labels))
    
        return feed
    
    async def _to_text(self, rule: config.RewriteRule, labels: dict[str, str]) -> str | None:  # audit:rewrite-route
        prompt = rule.prompt_t.format_map(labels) if rule.prompt_t else ""  # type: ignore[union-attr]
        system = rule.system_prompt_t.format_map(labels) if rule.system_prompt_t else None  # type: ignore[union-attr]  # audit:llm-system
        llm = self.llms.get(rule.llm)  # type: ignore[arg-type]
        if llm is None:
            return None
        return await llm.send_messages(input=prompt, system=system)     # type: ignore

    # audit:rewrite-filter
    async def _filter(self, rule: config.RewriteRule, labels: dict[str, str]) -> object | None:
        """正则不匹配标签值则丢弃整条feed。匹配则返回_KEEP。"""
        pattern = rule.prompt_t
        label_val = labels.get(rule.label)    # type: ignore
        if label_val is None or not re.search(pattern, label_val):      # type: ignore
            return None
        return _KEEP

    # audit:rewrite-replace
    async def _replace(self, rule: config.RewriteRule, labels: dict[str, str]) -> str | None:
        """对标签值做正则替换。"""
        label_val = labels.get(rule.label)  # type: ignore[arg-type]
        if label_val is None:
            return None
        return re.sub(rule.prompt_t, rule.replacement, label_val)  # type: ignore[arg-type]

    # audit:rewrite-set
    async def _set(self, rule: config.RewriteRule, labels: dict[str, str]) -> str | None:
        """直接设置标签值。"""
        return rule.value  # type: ignore[return-value]

    # audit:rewrite-crawl
    async def _crawl(self, rule: config.RewriteRule, labels: dict[str, str]) -> str | None:
        """抓取URL标签对应的网页正文。"""
        url = labels.get(rule.url_label)  # type: ignore[arg-type]
        if not url:
            return None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    return await resp.text()
        except Exception as e:
            logger.warning("crawl rule %r: failed to fetch %s: %s", rule.name, url, e)
            return None
