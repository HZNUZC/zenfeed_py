from zenfeed import config, llm
from .zenfeed import Feed, Labels

class RewritePipe:
    
    def __init__(self, config: list[config.RewriteRule], name2llm: dict[str, llm.LLM]):
        self.rules = config
        self.llms = name2llm

    async def rewrite(self, feed: Feed) -> Feed | None:

        labels = feed.get_labels().map()

        if labels is None:
            return None

        for rule in self.rules:
            # 构造prompt
            prompt = rule.prompt_t.format_map(labels or {})
            llm_name = rule.llm

            # 处理feed，拿到新标签的内容，追加到labels
            response = await self._route(rule.type)(llm_name, prompt)
            labels[rule.label] = response                       # type: ignore

            # 回写Feed
            feed.set_labels(Labels.from_map(labels))
    
        return feed
    
    def _route(self, type: config.RewriteType):
        # 根据type来路由具体操作
        if type == config.RewriteType.ToText:
            return self.to_text
        
    # TODO: 可以写工厂
    async def to_text(self, name: str, prompt: str):
        
        llm = self.llms.get(name)

        # TODO: 应该写进log或者抛错误
        if llm is None:
            return None
        
        return await llm.send_messages(prompt=prompt)