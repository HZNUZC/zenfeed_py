import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "python"))

from zenfeed import Feed, FeedStorage


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected!r}, got {actual!r}")


def main():
    feeds_data = [
        {
            "title": "Rust async deep dive",
            "source": "reddit",
            "type": "article",
            "content": "An exploration of async runtime internals",
        },
        {
            "title": "Python 3.14 released",
            "source": "hackernews",
            "type": "news",
            "content": "Major performance improvements in the new release",
        },
        {
            "title": "Building a TSDB from scratch",
            "source": "blog",
            "type": "article",
            "content": "How to design a time series database with columnar storage",
        },
        {
            "title": "Heterogeneous labels test",
            "source": "twitter",
            "type": "thread",
            "author": "jane_doe",
            "category": "systems",
        },
    ]

    base = 1_800_000_000
    times = [
        base,
        base + 3_600,
        base + 25 * 3_600,
        base + 2 * 3_600,
    ]

    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            fs = FeedStorage.open()

            for labels, feed_time in zip(feeds_data, times):
                fs.append([Feed.from_dict(labels, feed_time)])

            rust_ids = fs.query(("source", None), (None, None), False, None)
            assert_equal(len(rust_ids), len(feeds_data), "all feeds should be queryable")

            feeds = fs.get_feeds(list(reversed(rust_ids)))
            assert_equal(len(feeds), len(feeds_data), "get_feeds should return every requested feed")

            expected_by_source = {
                labels["source"]: (labels, feed_time)
                for labels, feed_time in zip(feeds_data, times)
            }

            for feed in feeds:
                labels = feed.get_labels()
                source = labels["source"]
                expected_labels, expected_time = expected_by_source[source]

                assert_equal(feed.time, expected_time, "feed time should come from feed_time chunk")
                assert_equal("feed_time" in labels, False, "feed_time should not be returned as a normal label")

                for key, val in expected_labels.items():
                    assert_equal(labels.get(key), val, f"label {key} should round-trip")

            print("ok")
        finally:
            os.chdir(old_cwd)


if __name__ == "__main__":
    main()
