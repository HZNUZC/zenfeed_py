import feedparser
import calendar
import time
import asyncio
import aiohttp
from zenfeed import config
from .zenfeed import Feed
from .kvstorage import KVStorage

class Scraper:

    def __init__(self, config: config.Scraper, kv: KVStorage | None = None):  # audit:etag
        self.rss_list = config.rss_list
        self.interval = config.interval
        self._kv = kv

    async def fetch_all(self, urls):  # audit:etag 非静态方法以访问_kv
        async with aiohttp.ClientSession() as session:
            tasks = [self._fetch_one(session, url) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            bodies = []
            for r in results:
                if isinstance(r, Exception):
                    bodies.append("")
                else:
                    bodies.append(r)
            return bodies

    async def _fetch_one(self, session, url):  # audit:etag
        headers = {}
        if self._kv:
            etag = self._kv.get(f"etag:{url}")
            lm = self._kv.get(f"lm:{url}")
            if etag:
                headers["If-None-Match"] = etag
            elif lm:
                headers["If-Modified-Since"] = lm

        async with session.get(url, headers=headers) as resp:
            if resp.status == 304:
                return ""
            if self._kv:
                if etag_h := resp.headers.get("ETag"):
                    self._kv.set(f"etag:{url}", etag_h)
                if lm_h := resp.headers.get("Last-Modified"):
                    self._kv.set(f"lm:{url}", lm_h)
            return await resp.text()
    
    @staticmethod
    def _remove_repeat(primary_feeds: list[Feed]) -> list[Feed]:
        seen_links = set()
        new_list = []
        for f in primary_feeds:
            if f.get_labels().get("link") not in seen_links:
                seen_links.add(f.get_labels().get("link"))
                new_list.append(f)
        return new_list

    async def scraper(self) -> list[Feed]:

        feeds: list[Feed] = []

        primary_feeds: list[Feed] = []
        
        urls = [rss.url for rss in self.rss_list]
        xmls = await self.fetch_all(urls)

        for xml in xmls:
            if not xml:
                continue  # audit:etag 304时跳过解析
            parse_res = feedparser.parse(xml)

            for entry in parse_res.entries:

                feed_labels = {
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "summary": entry.get("summary", ""),
                    "published": entry.get("published", ""),
                    "content": entry.get("content", ""),
                }

                parsed_time = entry.get("published_parsed", "")
                timestamp = int(time.time())

                if parsed_time:
                    timestamp = calendar.timegm(parsed_time)    # type: ignore
                
                feed = Feed.from_dict(feed_labels, timestamp)   # type: ignore
                primary_feeds.append(feed)

        feeds = Scraper._remove_repeat(primary_feeds=primary_feeds)

        return feeds