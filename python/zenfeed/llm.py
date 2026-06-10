import asyncio
from abc import ABC, abstractmethod
from .config import LLM as llm
from typing import Any
from openai import AsyncOpenAI

# LLM作为其他类型的llm的抽象基类
class Model(ABC):

    # 实例化时传递配置并初始化client
    def __init__(self, config: llm):
        self.name = config.name
        self.model_id = config.model_id
        self.max_concurrency = config.max_concurrency
        self.sem = asyncio.Semaphore(self.max_concurrency)
        self.client = AsyncOpenAI(api_key=config.provider.api_key, base_url=config.provider.api_base)

    # 封装调用逻辑
    @abstractmethod
    async def send_messages(self, input: str, system: str) -> Any | None :
        pass
    
class LLM(Model):

    async def send_messages(self, input: str, system: str | None = None) -> Any | None:  # audit:llm-system
        # 利用实例属性sem来做sendmessage接口限速
        async with self.sem:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": input})
            responses = await self.client.chat.completions.create(
                model=self.model_id,
                messages=messages,
            )

        return responses.choices[0].message.content

class Embedding(Model):
    # system 参数无实义，只是为了取消报错
    async def send_messages(self, input: str, system: str | None = None) -> Any | None:
        
        async with self.sem:
            responses = await self.client.embeddings.create(
                model=self.model_id,
                input=input,
            )
            return responses.data[0].embedding

class TTS(Model):

    async def send_messages(self, input: str, system: str | None = None) -> Any | None:
        
        async with self.sem:
            responses = await self.client.audio.speech.create(
                model=self.model_id,
                input=input,
                voice="alloy"
            )
            return responses.content

class LLMs:
    
    def __init__(self, config: list[llm]) -> None:
        self.name2llm: dict[str, Model] = {}
        for l in config:
            self.name2llm.update({l.name: model_type_route(l)})

    # 对外暴露get方法拿到实例
    def get(self, name: str) -> Model | None:
        return self.name2llm.get(name)
    
def model_type_route(config: llm) -> Model:
    if config.type == "tts":
        return TTS(config)
    if config.type == "general":
        return LLM(config)
    if config.type == "embed":
        return Embedding(config)
    # fallback
    return LLM(config)
