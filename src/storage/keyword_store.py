from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Iterable


@dataclass
class KeywordStore:
    file_path: Path
    _lock: Lock = field(default_factory=Lock)

    def __post_init__(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self._save({"manual_keywords": [], "excel_keywords": []})

    def _load(self) -> dict:
        with self.file_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, payload: dict) -> None:
        with self.file_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def get_all(self) -> dict:
        with self._lock:
            payload = self._load()
            payload["active_keywords"] = self._merge_keywords(payload)
            return payload

    def replace_excel_keywords(self, keywords: Iterable[str]) -> dict:
        cleaned = _normalize_keywords(keywords)
        with self._lock:
            payload = self._load()
            payload["excel_keywords"] = cleaned
            self._save(payload)
            payload["active_keywords"] = self._merge_keywords(payload)
            return payload

    def add_manual_keyword(self, keyword: str) -> dict:
        cleaned = keyword.strip()
        if not cleaned:
            raise ValueError("关键词不能为空")
        with self._lock:
            payload = self._load()
            manual = payload.get("manual_keywords", [])
            if cleaned not in manual:
                manual.append(cleaned)
            payload["manual_keywords"] = manual
            self._save(payload)
            payload["active_keywords"] = self._merge_keywords(payload)
            return payload

    @staticmethod
    def _merge_keywords(payload: dict) -> list[str]:
        merged = payload.get("manual_keywords", []) + payload.get("excel_keywords", [])
        # Preserve order while removing duplicates.
        return list(dict.fromkeys(_normalize_keywords(merged)))


def _normalize_keywords(items: Iterable[str]) -> list[str]:
    normalized = []
    for item in items:
        if item is None:
            continue
        cleaned = str(item).strip()
        if cleaned:
            normalized.append(cleaned)
    return list(dict.fromkeys(normalized))
