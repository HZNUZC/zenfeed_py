import feedparser
import calendar
import time
import asyncio
import aiohttp
from zenfeed import config
from .zenfeed import Feed

class Scraper:

    def __init__(self, config: config.Scraper):
        self.rss_list = config.rss_list
        self.interval = config.interval

    @staticmethod
    async def fetch_all(urls):
        async with aiohttp.ClientSession() as session:
            tasks = [Scraper.fetch_one(session, url) for url in urls]
            return await asyncio.gather(*tasks)

    @staticmethod
    async def fetch_one(session, url):
        async with session.get(url) as resp:
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
        xmls = await Scraper.fetch_all(urls)

        for xml in xmls:
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