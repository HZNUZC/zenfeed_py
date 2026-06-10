import asyncio
from zenfeed import FeedStorage # type: ignore
from zenfeed.config import load
from zenfeed.scraper import Scraper
from zenfeed.rewrite import RewritePipe
from zenfeed.llm import LLMs
from zenfeed.scheduler import Scheduler
from zenfeed.notifier import Notifier
from zenfeed.kvstorage import KVStorage

CONFIG_FILE_PATH = ".zenfeed/config.json"

# 先加载配置，再分别注入依赖
print("loading config file...")
config = load(CONFIG_FILE_PATH)
print("config loaded")

llms = LLMs(config.llms_config)

storage_cfg = config.storage_config
# audit:rust-bridge 把window/data_dir传给Rust
fs = FeedStorage.open(
    manifest_path=f"{storage_cfg.data_dir}/manifest.json",
    window=storage_cfg.window,
)

kv = KVStorage(f"{storage_cfg.data_dir}/kv.json")  # audit:kvstorage

scraper = Scraper(config.scraper_config, kv)  # audit:etag

rp = RewritePipe(config.rewrite_rules, llms)

nf = Notifier(config.receiver_config, config.channels_config)

# scheduler作为核心控制中枢，注入全部依赖
scheduler = Scheduler(
    config.scheduler_rules,
    config.watch_rules,  # audit:watch-config
    fs, scraper, rp, nf,
)

# 启动系统调度流程
asyncio.run(scheduler.start())