import asyncio
import aiohttp
import aiosmtplib
from datetime import datetime
from abc import ABC, abstractmethod
from .zenfeed import Feed
from .config import EmailContent, ContentTemplate, ChannelsConfig, ReceiverConfig
from .config import EmailChannel as ec
from .config import WebhookChannel as wc
from email.message import EmailMessage

# 抽象基类
class Channel(ABC):
    
    @abstractmethod
    async def send(self, feed_slice: list[Feed]):
        pass

    # 对于拥有ContentTemplate的类
    def _build_content(self, content_template: ContentTemplate, feeds: list[Feed]) -> str :
        content = []
        for f in feeds:
            content.append(content_template.item_template.format_map(f.get_labels().map() or {}))
        return content_template.separator.join(content)

class EmailChannel(Channel):

    def __init__(self, config: ec) -> None:
        self.name: str = config.name
        self.url: str = config.url
        self.port: int = config.port
        self.user: str = config.user
        self.passwd: str = config.passwd
        self.mail_meta: list = config.mail_meta
        self.mail_content_t: EmailContent = config.mail_content_t
    
    async def send(self, feed_slice: list[Feed]):
        
        msg = EmailMessage()
        # 程序缺乏这个数组的长度校验，按照职责划分，应该放到config.py
        # TODO: 数组长度校验
        msg["From"] = self.mail_meta[0]
        msg["To"] = ", ".join(self.mail_meta[1:])
        msg["Subject"] = self.mail_content_t.subject

        msg.set_content(self._build_content(self.mail_content_t.content, feed_slice))

        # 发送请求
        await aiosmtplib.send(msg, hostname=self.url, username=self.user, password=self.passwd, port=self.port)

class WebhookChannel(Channel):
    
    def __init__(self, config: wc) -> None:
        self.name: str = config.name
        self.url: str = config.url
        self.http_method: str = config.http_method
        self.body_template: ContentTemplate = config.body_template

    async def send(self, feed_slice: list[Feed]):

        async with aiohttp.ClientSession() as session:
            payload = {
                "time": datetime.now().isoformat(),
                "content": self._build_content(self.body_template, feed_slice)
            }
            async with session.request(method=self.http_method, url=self.url, json=payload) as resp:
                resp.raise_for_status()

# channel的聚合管理中枢
class Channels:
    
    def __init__(self, config: ChannelsConfig) -> None:
        self.name2channel: dict[str, Channel] = {}
        # update方法在key重合的情况下会覆盖，因此我们规定名字不能重合，不做兼容层
        for s in config.smtp:
            self.name2channel.update({s.name: EmailChannel(s)})
        for w in config.webhook:
            self.name2channel.update({w.name: WebhookChannel(w)})

    # 对外暴露一个GET方法让外部可以拿到channel的实例
    def get(self, name) -> Channel | None:
        return self.name2channel.get(name)

# 策略聚合，调用channel
# 需要实现feed列表切片
class Receiver:
    
    def __init__(self, config: ReceiverConfig, channels: Channels) -> None:
        self.name = config.name
        # 事实上，get方法的确可能返回None，这不是我们期望的，我们应该在config里校验这一点
        # TODO: config里需要添加配置逻辑的校验，因为这里根本不合适返回None
        self.channel = channels.get(config.channel)
        self.slice_size = config.slice_size

    # 把feeds列表切出来放到列表里
    def _feed_slice(self, feeds: list[Feed]) -> list[list[Feed]]:
        
        s = 0
        e = self.slice_size
        feed_slice: list[list[Feed]] = []

        while s < len(feeds):
            if e <= len(feeds):
                feed_slice.append(feeds[s:e])
            else:
                feed_slice.append(feeds[s:])
            s += self.slice_size
            e += self.slice_size
        
        return feed_slice
    
    # 其实也可以写成同步方法
    # 不过这里直接贴合channel的send里的异步方法，将异步函数的调度权集中到notifier吧
    async def send_channel(self, feeds: list[Feed]):
        
        # 根据所有要发的feed切片来创建出异步任务
        tasks = [asyncio.create_task(self.channel.send(flice)) for flice in self._feed_slice(feeds)]     # type: ignore
        await asyncio.gather(*tasks)

# 持有receivers，最上层的建筑
class Notifier:
    
    def __init__(self, config: list[ReceiverConfig], channels_config: ChannelsConfig) -> None:
        self.name2receiver: dict[str, Receiver] = {}
        self.channels = Channels(channels_config)
        for rv in config:
            self.name2receiver.update({rv.name: Receiver(rv, self.channels)})

    async def send(self, feeds: list[Feed], receiver: str):
        
        # 根据传递进来的名称路由
        r = self.name2receiver.get(receiver)
        if r is not None:
            await r.send_channel(feeds)