import asyncio
import logging
from croniter import croniter
from datetime import datetime
from .zenfeed import FeedStorage, Feed
from .config import Periodic, Watch
from .scraper import Scraper
from .rewrite import RewritePipe
from .notifier import Notifier

logger = logging.getLogger(__name__)

class Scheduler:
    
    # 对象初始化时注入依赖
    def __init__(self, periodics: list[Periodic], watches: list[Watch], fs: FeedStorage, scraper: Scraper, rewrite_pipe: RewritePipe, notifier: Notifier):  # audit:watch-scheduler
        self.periodics = periodics
        self.watches = watches
        self.fs = fs
        self.sp = scraper
        self.rp = rewrite_pipe
        self.nf = notifier
        # audit:watch-dedup 记录每个watch已通知过的feed ID
        self._watch_seen: dict[str, set[int]] = {w.name: set() for w in watches}

    async def _run_one_periodic(self, rule: Periodic):
        
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
                print("准备发送")
                await self.send_notifier(feeds, rule.receiver)
                print("sending suceessfully")
            else:
                print("没有feed符合条件")

    # audit:watch-scheduler
    async def _run_one_watch(self, rule: Watch):
        seen = self._watch_seen[rule.name]
        while True:
            await asyncio.sleep(rule.interval)

            f_ids = []
            v_ids = []

            if rule.filt_query_arg:
                filt_arg = rule.filt_query_arg
                f_ids = self.fs.query(filt_arg.filter, filt_arg.s2e, filt_arg.mode, filt_arg.limit)

            if rule.vec_query_arg:
                vec_arg = rule.vec_query_arg
                v_ids = self.fs.vector_query(vec_arg.vector, vec_arg.s2e, vec_arg.limit)

            ids = set(v_ids) | set(f_ids)
            new_ids = [i for i in ids if i not in seen]

            if new_ids:
                feeds = self.fs.get_feeds(new_ids)
                if feeds is not None:
                    seen.update(new_ids)
                    logger.info("watch rule %r: %d new feeds found, sending", rule.name, len(feeds))
                    await self.send_notifier(feeds, rule.receiver)
    
    async def _run_scrape_loop(self):
        while True:
            feeds = await self.sp.scraper()
            print("scrapering")
            tasks = [self.rp.rewrite(feed) for feed in feeds]
            feeds = await asyncio.gather(*tasks)
            feeds = [f for f in feeds if f is not None]
            self.fs.append(feeds)
            print("saved")               
            await asyncio.sleep(self.sp.interval)

    async def start(self):
        tasks = []
        for rule in self.periodics:
            tasks.append(asyncio.create_task(self._run_one_periodic(rule)))
        for rule in self.watches:
            tasks.append(asyncio.create_task(self._run_one_watch(rule)))
        tasks.append(asyncio.create_task(self._run_scrape_loop()))
        await asyncio.gather(*tasks)

    async def send_notifier(self, feeds: list[Feed], receiver: str):
        await self.nf.send(feeds, receiver)