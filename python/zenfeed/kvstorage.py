import json
from pathlib import Path


# audit:kvstorage 基于JSON文件的键值存储
class KVStorage:

    def __init__(self, path: str):
        self._path = Path(path)
        self._dirty = False
        self._data: dict[str, str] = {}
        self._load()

    def _load(self):
        if self._path.exists():
            with open(self._path, "r") as f:
                self._data = json.load(f)

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(self._data, f)

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def set(self, key: str, value: str):
        self._data[key] = value
        self._save()

    def has(self, key: str) -> bool:
        return key in self._data
