import asyncio
from zenfeed import FeedStorage # type: ignore
from zenfeed.config import load
from zenfeed.scraper import Scraper
from zenfeed.rewrite import RewritePipe
from zenfeed.llm import LLM
from zenfeed.scheduler import Scheduler

CONFIG_FILE_PATH = ".zenfeed/config.json"

# 先加载配置，再分别注入依赖
print("loading config file...")
config = load(CONFIG_FILE_PATH)
print("config loaded")

name2llm = {}
for c in config.llm_config:
    name2llm[c.name] = LLM(c)

fs = FeedStorage()

scraper = Scraper(config.scraper_config)

rp = RewritePipe(config.rewrite_rules, name2llm)

scheduler = Scheduler(config.scheduler_rules, fs, scraper, rp)

# 启动系统调度流程
asyncio.run(scheduler.start())