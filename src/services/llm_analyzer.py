from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib import error, request


@dataclass
class QwenConfig:
    api_key: str | None = None
    model_name: str = "qwen3.5-plus"
    endpoint: str = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    timeout_s: int = 30


class QwenAnalyzer:
    """Analyzer with a real Qwen API integration + deterministic local stats fallback."""

    def __init__(self, config: QwenConfig | None = None) -> None:
        self.config = config or QwenConfig()

    def analyze_posts(self, posts: list[dict[str, str]], keywords: list[str]) -> dict[str, Any]:
        keyword_stats = self._local_keyword_stats(posts, keywords)
        llm_summary, llm_error = self._call_qwen(posts, keywords)

        result: dict[str, Any] = {
            "model_provider": "qwen",
            "model_name": self.config.model_name,
            "summary": {
                "post_count": len(posts),
                "keyword_count": len(keywords),
                "total_mentions": sum(item["mentions"] for item in keyword_stats),
            },
            "keywords": sorted(keyword_stats, key=lambda item: item["mentions"], reverse=True),
            "llm_enabled": bool(self.config.api_key),
        }
        if llm_summary:
            result["llm_summary"] = llm_summary
        if llm_error:
            result["llm_error"] = llm_error
        return result

    def _local_keyword_stats(self, posts: list[dict[str, str]], keywords: list[str]) -> list[dict[str, Any]]:
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
        return keyword_stats

    def _call_qwen(self, posts: list[dict[str, str]], keywords: list[str]) -> tuple[str | None, str | None]:
        if not self.config.api_key:
            return None, "未配置 Qwen API Key，已返回本地统计结果"

        payload = {
            "model": self.config.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是小红书服装文案分析助手。请基于给定帖子和关键词，"
                        "输出3条中文洞察，每条不超过30字，关注风格趋势与用户偏好。"
                    ),
                },
                {"role": "user", "content": self._build_user_prompt(posts, keywords)},
            ],
            "temperature": 0.3,
        }

        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            self.config.endpoint,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.config.timeout_s) as resp:
                body = resp.read().decode("utf-8")
            parsed = json.loads(body)
            content = (
                parsed.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            if not content:
                return None, "Qwen 返回内容为空，已返回本地统计结果"
            return content, None
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else str(exc)
            return None, f"Qwen 请求失败: HTTP {exc.code} {detail[:180]}"
        except Exception as exc:
            return None, f"Qwen 请求失败: {exc}"

    @staticmethod
    def _build_user_prompt(posts: list[dict[str, str]], keywords: list[str]) -> str:
        post_lines = []
        for idx, post in enumerate(posts[:40], start=1):
            post_lines.append(
                f"{idx}. 标题: {post.get('title', '')} | 内容: {post.get('content', '')}"
            )
        return (
            "关键词：" + "、".join(keywords[:50]) + "\n"
            "帖子样本：\n" + "\n".join(post_lines)
        )
