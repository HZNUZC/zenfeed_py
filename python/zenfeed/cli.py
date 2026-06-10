import click
import asyncio
from zenfeed import FeedStorage
from zenfeed.config import load
from zenfeed.scraper import Scraper
from zenfeed.rewrite import RewritePipe
from zenfeed.llm import LLMs
from zenfeed.scheduler import Scheduler
from zenfeed.notifier import Notifier
from zenfeed.kvstorage import KVStorage

CONFIG_FILE_PATH = ".zenfeed/config.json"

@click.group()
def cli():
    pass

@cli.command()
@click.option('--config', 'path', default=CONFIG_FILE_PATH, help="")
def run(path):

    # 先加载配置，再分别注入依赖
    print("loading config file...")
    config = load(path)
    print("config loaded")

    # 拉起各个实例依赖
    llms = LLMs(config.llms_config)
    storage_cfg = config.storage_config
    
    fs = FeedStorage.open(
        manifest_path=f"{storage_cfg.data_dir}/manifest.json",
        window=storage_cfg.window,
    )
    kv = KVStorage(f"{storage_cfg.data_dir}/kv.json")  # audit:kvstorage
    scraper = Scraper(config.scraper_config, kv)  # audit:etag
    rp = RewritePipe(config.rewrite_rules, llms)
    nf = Notifier(config.receiver_config, config.channels_config)

    # 中枢调度器
    scheduler = Scheduler(
        config.scheduler_rules,
        config.watch_rules,  # audit:watch-config
        fs, scraper, rp, nf,
    )

    # 启动系统调度流程
    asyncio.run(scheduler.start())

if __name__ == "__main__":
    cli()