import asyncio
from croniter import croniter
from datetime import datetime
from .zenfeed import FeedStorage, Feed
from .config import Periodic
from .scraper import Scraper
from .rewrite import RewritePipe
from .notifier import Notifier

class Scheduler:
    
    # 对象初始化时注入依赖
    def __init__(self, rules: list[Periodic], fs: FeedStorage, scraper: Scraper, rewrite_pipe: RewritePipe, notifier: Notifier):
        self.rules = rules
        self.fs = fs
        self.sp = scraper
        self.rp = rewrite_pipe
        self.nf = notifier

    async def _run_one_rule(self, rule: Periodic):
        
        while True:
            now = datetime.now()
            cron = croniter(rule.cron, now)
            next_time = cron.get_next(datetime)
            wait_time = (next_time - now).total_seconds()
            await asyncio.sleep(wait_time)

            f_ids = []
            v_ids = []

            if rule.filt_query_arg:
                filt_arg = rule.filt_query_arg
                f_ids = self.fs.query(filt_arg.filter, filt_arg.s2e, filt_arg.mode, filt_arg.limit)

            if rule.vec_query_arg:
                vec_arg = rule.vec_query_arg
                v_ids = self.fs.vector_query(vec_arg.vector, vec_arg.s2e, vec_arg.limit)

            feeds = self.fs.get_feeds(list(set(v_ids) | set(f_ids)))
            if feeds is not None:
                await self.send_notifier(feeds, rule.receiver)
    
    async def _run_scrape_loop(self):
        while True:
            feeds = await self.sp.scraper()
            tasks = [self.rp.rewrite(feed) for feed in feeds]
            feeds = await asyncio.gather(*tasks)
            feeds = [f for f in feeds if f is not None]
            self.fs.append(feeds)               
            await asyncio.sleep(self.sp.interval)

    async def start(self):
        tasks = []
        for rule in self.rules:
            tasks.append(asyncio.create_task(self._run_one_rule(rule)))
        tasks.append(asyncio.create_task(self._run_scrape_loop()))
        await asyncio.gather(*tasks)

    async def send_notifier(self, feeds: list[Feed], receiver: str):
        await self.nf.send(feeds, receiver)