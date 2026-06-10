import asyncio

import pytest
from zenfeed import Feed
from zenfeed.config import RSS, Scraper as ScraperConfig
from zenfeed.scraper import Scraper


RSS_XML = """\
<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
  <channel>
    <title>Example Feed</title>
    <item>
      <title>first</title>
      <link>https://example.invalid/1</link>
      <description>summary one</description>
      <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
    </item>
    <item>
      <title>duplicate</title>
      <link>https://example.invalid/1</link>
      <description>summary duplicate</description>
      <pubDate>Tue, 02 Jan 2024 00:00:00 GMT</pubDate>
    </item>
    <item>
      <title>second</title>
      <link>https://example.invalid/2</link>
      <description>summary two</description>
      <pubDate>Wed, 03 Jan 2024 00:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def _labels(feed: Feed) -> dict[str, str]:
    labels = feed.get_labels().map()
    assert labels is not None
    return labels


def test_remove_repeat_keeps_first_feed_for_each_link() -> None:
    first = Feed.from_dict({"title": "first", "link": "https://example.invalid/1"}, 1)
    duplicate = Feed.from_dict(
        {"title": "duplicate", "link": "https://example.invalid/1"},
        2,
    )
    second = Feed.from_dict({"title": "second", "link": "https://example.invalid/2"}, 3)

    result = Scraper._remove_repeat([first, duplicate, second])

    assert result == [first, second]


def test_scraper_parses_feeds_and_removes_duplicate_links(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch_all(urls: list[str]) -> list[str]:
        assert urls == ["https://example.invalid/rss"]
        return [RSS_XML]

    monkeypatch.setattr(Scraper, "fetch_all", staticmethod(fake_fetch_all))
    scraper = Scraper(
        ScraperConfig(
            interval=30,
            rss_list=[RSS(name="example", url="https://example.invalid/rss")],
        )
    )

    feeds = asyncio.run(scraper.scraper())

    assert len(feeds) == 2

    first_labels = _labels(feeds[0])
    second_labels = _labels(feeds[1])
    assert first_labels["title"] == "first"
    assert first_labels["summary"] == "summary one"
    assert first_labels["link"] == "https://example.invalid/1"
    assert feeds[0].time == 1704067200
    assert second_labels["title"] == "second"
    assert second_labels["link"] == "https://example.invalid/2"
