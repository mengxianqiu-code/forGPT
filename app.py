from __future__ import annotations

import json
import mimetypes
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import cgi

from src.services.excel_parser import ExcelFormatError, parse_keywords_excel, parse_posts_excel
from src.services.llm_analyzer import QwenAnalyzer
from src.storage.keyword_store import KeywordStore


@dataclass
class AppState:
    posts: list[dict[str, str]] = field(default_factory=list)


ROOT = Path(__file__).parent
state = AppState()
keyword_store = KeywordStore(Path("data/keywords.json"))
analyzer = QwenAnalyzer()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            return self._serve_file(ROOT / "templates" / "index.html", "text/html; charset=utf-8")
        if self.path.startswith("/static/"):
            local = ROOT / self.path.lstrip("/")
            ctype, _ = mimetypes.guess_type(str(local))
            return self._serve_file(local, ctype or "application/octet-stream")
        if self.path == "/api/settings":
            return self._json(200, keyword_store.get_all())
        return self._json(404, {"error": "Not found"})

    def do_POST(self):
        if self.path == "/api/settings/keywords/manual":
            return self._manual_keyword()
        if self.path == "/api/settings/keywords/upload":
            return self._upload_keywords()
        if self.path == "/api/posts/upload":
            return self._upload_posts()
        if self.path == "/api/analyze":
            return self._analyze()
        return self._json(404, {"error": "Not found"})

    def _upload_keywords(self):
        file_bytes = self._read_multipart_file()
        if not file_bytes:
            return self._json(400, {"error": "请上传关键词 Excel 文件"})
        try:
            keywords = parse_keywords_excel(file_bytes)
            payload = keyword_store.replace_excel_keywords(keywords)
            return self._json(200, payload)
        except ExcelFormatError as exc:
            return self._json(400, {"error": str(exc)})

    def _upload_posts(self):
        file_bytes = self._read_multipart_file()
        if not file_bytes:
            return self._json(400, {"error": "请上传帖子 Excel 文件"})
        try:
            state.posts = parse_posts_excel(file_bytes)
            return self._json(200, {"post_count": len(state.posts)})
        except ExcelFormatError as exc:
            return self._json(400, {"error": str(exc)})

    def _manual_keyword(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0") or 0))
        try:
            data = json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            data = {}
        try:
            payload = keyword_store.add_manual_keyword(str(data.get("keyword", "")))
            return self._json(200, payload)
        except ValueError as exc:
            return self._json(400, {"error": str(exc)})

    def _analyze(self):
        if not state.posts:
            return self._json(400, {"error": "请先上传帖子 Excel"})
        active_keywords = keyword_store.get_all().get("active_keywords", [])
        if not active_keywords:
            return self._json(400, {"error": "请先在设置中配置关键词"})
        return self._json(200, analyzer.analyze_posts(state.posts, active_keywords))

    def _read_multipart_file(self) -> bytes:
        ctype = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ctype:
            return b""
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": ctype,
            },
        )
        if "file" not in form:
            return b""
        file_item = form["file"]
        if getattr(file_item, "file", None) is None:
            return b""
        return file_item.file.read()

    def _serve_file(self, path: Path, content_type: str):
        if not path.exists() or not path.is_file():
            return self._json(404, {"error": "Not found"})
        payload = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, status: int, payload: dict):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", 8000), Handler)
    print("Server running on http://0.0.0.0:8000")
    server.serve_forever()
