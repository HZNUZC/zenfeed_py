import asyncio
from collections.abc import Mapping

from zenfeed import Feed
from zenfeed.config import RewriteRule
from zenfeed.rewrite import RewritePipe


class FakeLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []
        self.system_prompts: list[str | None] = []

    async def send_messages(self, input: str, system: str | None = None) -> str:  # audit:llm-system
        self.prompts.append(input)
        self.system_prompts.append(system)
        return self.response


class FakeLLMs:
    def __init__(self, mapping: Mapping[str, FakeLLM]) -> None:
        self.mapping = mapping

    def get(self, name: str) -> FakeLLM | None:
        return self.mapping.get(name)


def _labels(feed: Feed) -> dict[str, str]:
    labels = feed.get_labels().map()
    assert labels is not None
    return labels


def test_rewrite_renders_prompt_calls_llm_and_writes_new_label() -> None:
    fake_llm = FakeLLM("rewritten content")
    rule = RewriteRule(
        name="summary",
        type="transform.to_text",
        llm="deepseek",
        prompt_t="summary={summary}; content={content}",
        label="ai_summary",
    )
    pipe = RewritePipe([rule], FakeLLMs({"deepseek": fake_llm}))  # type: ignore
    feed = Feed.from_dict(
        {
            "summary": "short",
            "content": "full",
        },
        1,
    )

    result = asyncio.run(pipe.rewrite(feed))

    assert result is feed
    assert fake_llm.prompts == ["summary=short; content=full"]
    assert _labels(feed)["ai_summary"] == "rewritten content"


def test_rewrite_returns_none_for_feed_without_labels() -> None:
    pipe = RewritePipe([], FakeLLMs({}))  # type: ignore

    result = asyncio.run(pipe.rewrite(Feed(1)))

    assert result is None


def test_rewrite_skips_rule_when_llm_name_is_unknown() -> None:  # audit:rewrite-error
    rule = RewriteRule(
        name="summary",
        type="transform.to_text",
        llm="missing",
        prompt_t="{title}",
        label="ai_summary",
    )
    pipe = RewritePipe([rule], FakeLLMs({}))  # type: ignore
    feed = Feed.from_dict({"title": "hello"}, 1)

    result = asyncio.run(pipe.rewrite(feed))

    assert result is feed
    assert "ai_summary" not in _labels(feed)

def test_rewrite_filter_drops_feed_when_pattern_does_not_match() -> None:  # audit:rewrite-filter
    rule = RewriteRule(
        name="keep_ai",
        type="filter",
        prompt_t=r"\bAI\b",
        label="title",
    )
    pipe = RewritePipe([rule], FakeLLMs({}))  # type: ignore
    feed = Feed.from_dict({"title": "hello world"}, 1)

    result = asyncio.run(pipe.rewrite(feed))

    assert result is None

def test_rewrite_replace_modifies_label_value() -> None:  # audit:rewrite-replace
    rule = RewriteRule(
        name="sanitize",
        type="replace",
        prompt_t=r"bad",
        replacement="good",
        label="title",
    )
    pipe = RewritePipe([rule], FakeLLMs({}))  # type: ignore
    feed = Feed.from_dict({"title": "bad apple"}, 1)

    result = asyncio.run(pipe.rewrite(feed))

    assert result is feed
    assert _labels(feed)["title"] == "good apple"

def test_rewrite_set_writes_fixed_value() -> None:  # audit:rewrite-set
    rule = RewriteRule(
        name="source",
        type="set",
        value="rss",
        label="source",
    )
    pipe = RewritePipe([rule], FakeLLMs({}))  # type: ignore
    feed = Feed.from_dict({"title": "test"}, 1)

    result = asyncio.run(pipe.rewrite(feed))

    assert result is feed
    assert _labels(feed)["source"] == "rss"
