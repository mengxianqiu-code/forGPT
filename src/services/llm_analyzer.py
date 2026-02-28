from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class QwenConfig:
    api_key: str | None = None
    model_name: str | None = None
    endpoint: str = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


class QwenAnalyzer:
    """Reserved integration point for Qwen LLM-based analysis.

    Later you can inject real API logic inside `analyze_posts` without
    changing route handlers.
    """

    def __init__(self, config: QwenConfig | None = None) -> None:
        self.config = config or QwenConfig()

    def analyze_posts(self, posts: list[dict[str, str]], keywords: list[str]) -> dict[str, Any]:
        # Placeholder strategy: local deterministic counting.
        # Replace with a Qwen request flow in future iterations.
        keyword_stats = []
        for keyword in keywords:
            hits = 0
            related = []
            for item in posts:
                text = f"{item.get('title', '')}\n{item.get('content', '')}"
                count = text.lower().count(keyword.lower())
                if count:
                    hits += count
                    related.append({"title": item.get("title", ""), "count": count})
            keyword_stats.append(
                {
                    "keyword": keyword,
                    "mentions": hits,
                    "post_hits": len(related),
                    "sample_posts": related[:3],
                }
            )

        return {
            "model_provider": "qwen",
            "model_name": self.config.model_name or "待配置",
            "summary": {
                "post_count": len(posts),
                "keyword_count": len(keywords),
                "total_mentions": sum(item["mentions"] for item in keyword_stats),
            },
            "keywords": sorted(keyword_stats, key=lambda item: item["mentions"], reverse=True),
        }
