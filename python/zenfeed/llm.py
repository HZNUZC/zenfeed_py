import asyncio
from zenfeed import config
from openai import AsyncOpenAI

class LLM:

    # 实例化时传递配置并初始化client
    def __init__(self, config: config.LLM):
        self.name = config.name
        self.model_id = config.model_id
        self.max_concurrency = config.max_concurrency
        self.sem = asyncio.Semaphore(self.max_concurrency)
        self.client = AsyncOpenAI(api_key=config.provider.api_key, base_url=config.provider.api_base)

    # 封装调用逻辑
    async def send_messages(self, prompt: str) -> str | None :
        
        # 利用实例属性sem来做sendmessage接口限速
        async with self.sem:
            # TODO: 构造合适的系统提示词
            responses = await self.client.chat.completions.create(
                model=self.model_id,
                messages=[{"role": "user", "content": prompt}],
            )

        return responses.choices[0].message.content