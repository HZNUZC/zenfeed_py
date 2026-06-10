from pathlib import Path

from zenfeed.kvstorage import KVStorage


def test_set_and_get(tmp_path: Path) -> None:
    path = tmp_path / "kv.json"
    kv = KVStorage(str(path))
    kv.set("foo", "bar")
    assert kv.get("foo") == "bar"


def test_get_missing_returns_none(tmp_path: Path) -> None:
    kv = KVStorage(str(tmp_path / "kv.json"))
    assert kv.get("missing") is None


def test_has(tmp_path: Path) -> None:
    kv = KVStorage(str(tmp_path / "kv.json"))
    kv.set("a", "1")
    assert kv.has("a")
    assert not kv.has("b")


def test_persistence(tmp_path: Path) -> None:
    path = tmp_path / "kv.json"
    kv1 = KVStorage(str(path))
    kv1.set("key", "val")

    kv2 = KVStorage(str(path))
    assert kv2.get("key") == "val"
