import json
from pathlib import Path
from typing import Any

import pytest

from zenfeed.config import LLMType, RewriteType, load


def _base_config() -> dict[str, Any]:
    return {
        "scraper_config": {
            "interval": 60,
            "rss_list": [
                {
                    "name": "HN",
                    "url": "https://hnrss.org/frontpage",
                }
            ],
        },
        "llms_config": [
            {
                "name": "deepseek",
                "model_id": "deepseek-chat",
                "type": "general",
                "max_concurrency": 2,
                "provider": {
                    "api_base": "${DEEPSEEK_BASE_URL}",
                    "api_key": "${DEEPSEEK_API_KEY}",
                },
            }
        ],
        "rewrite_rules": [
            {
                "name": "summary",
                "type": "transform.to_text",
                "llm": "deepseek",
                "prompt_t": "{summary}",
                "label": "ai_summary",
            }
        ],
        "scheduler_rules": [],
        "channels_config": {
            "smtp": [],
            "webhook": [
                {
                    "name": "hook",
                    "url": "https://example.invalid/webhook",
                    "body_template": {
                        "item_template": "{title}",
                        "separator": "\n",
                    },
                }
            ],
        },
        "receiver_config": [
            {
                "name": "daily",
                "channel": "hook",
                "slice_size": 10,
            }
        ],
    }


def test_load_resolves_env_placeholders_and_validates_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.example.invalid")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret")

    path = tmp_path / "config.json"
    path.write_text(json.dumps(_base_config()), encoding="utf-8")

    cfg = load(str(path))

    assert cfg.scraper_config.interval == 60
    assert cfg.llms_config[0].type is LLMType.General
    assert cfg.llms_config[0].provider.api_base == "https://api.example.invalid"
    assert cfg.llms_config[0].provider.api_key == "secret"
    assert cfg.rewrite_rules[0].type is RewriteType.ToText
    assert cfg.channels_config.webhook[0].http_method == "POST"
    assert cfg.receiver_config[0].slice_size == 10
    assert cfg.watch_rules == []           # audit:watch-config
    assert cfg.storage_config.window == 90000  # audit:storage-config
    assert cfg.storage_config.data_dir == ".zenfeed"


def test_load_raises_when_env_placeholder_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.example.invalid")

    path = tmp_path / "config.json"
    path.write_text(json.dumps(_base_config()), encoding="utf-8")

    with pytest.raises(ValueError, match="Missing environment variable: DEEPSEEK_API_KEY"):
        load(str(path))
