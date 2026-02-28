from __future__ import annotations

from io import StringIO
from typing import Iterable
from zipfile import ZipFile
import csv
import re
import xml.etree.ElementTree as ET

REQUIRED_POST_COLUMNS = ["title", "content"]


class ExcelFormatError(ValueError):
    pass


def parse_posts_excel(binary: bytes) -> list[dict]:
    rows = _read_table(binary)
    if not rows:
        raise ExcelFormatError("帖子 Excel 没有可用数据")

    header = [str(c).strip().lower() for c in rows[0]]
    idx_map = {name: i for i, name in enumerate(header)}
    missing = [c for c in REQUIRED_POST_COLUMNS if c not in idx_map]
    if missing:
        raise ExcelFormatError(f"帖子 Excel 缺少列: {', '.join(missing)}")

    output = []
    for row in rows[1:]:
        title = _safe_text(_get_cell(row, idx_map["title"]))
        content = _safe_text(_get_cell(row, idx_map["content"]))
        if title or content:
            output.append({"title": title, "content": content})

    if not output:
        raise ExcelFormatError("帖子 Excel 没有可用数据")
    return output


def parse_keywords_excel(binary: bytes) -> list[str]:
    rows = _read_table(binary)
    if len(rows) <= 1:
        return []
    first_col = [_safe_text(_get_cell(row, 0)) for row in rows[1:]]
    return _deduplicate(first_col)


def _read_table(binary: bytes) -> list[list[str]]:
    if binary[:2] == b"PK":
        return _read_xlsx(binary)
    return _read_csv(binary)


def _read_csv(binary: bytes) -> list[list[str]]:
    try:
        text = binary.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ExcelFormatError("无法解析文件，请上传 UTF-8 编码 CSV 或 xlsx") from exc
    reader = csv.reader(StringIO(text))
    rows = [list(row) for row in reader if any(str(c).strip() for c in row)]
    return rows


def _read_xlsx(binary: bytes) -> list[list[str]]:
    try:
        import io

        with ZipFile(io.BytesIO(binary)) as zf:
            shared = _parse_shared_strings(zf)
            sheet = _find_first_sheet_path(zf)
            return _parse_sheet_rows(zf.read(sheet), shared)
    except Exception as exc:
        raise ExcelFormatError("无法解析 xlsx 文件") from exc


def _find_first_sheet_path(zf: ZipFile) -> str:
    candidates = [
        "xl/worksheets/sheet1.xml",
        "xl/worksheets/sheet.xml",
    ]
    for c in candidates:
        if c in zf.namelist():
            return c
    for name in zf.namelist():
        if name.startswith("xl/worksheets/") and name.endswith(".xml"):
            return name
    raise ExcelFormatError("xlsx 中未找到工作表")


def _parse_shared_strings(zf: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    values = []
    for si in root.findall("x:si", ns):
        text = "".join((t.text or "") for t in si.findall(".//x:t", ns))
        values.append(text)
    return values


def _parse_sheet_rows(sheet_xml: bytes, shared: list[str]) -> list[list[str]]:
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    root = ET.fromstring(sheet_xml)
    rows = []
    for row in root.findall(".//x:sheetData/x:row", ns):
        row_cells: dict[int, str] = {}
        for c in row.findall("x:c", ns):
            ref = c.attrib.get("r", "A1")
            col = _col_to_index(re.match(r"([A-Z]+)", ref).group(1))
            cell_type = c.attrib.get("t")
            v = c.find("x:v", ns)
            raw = (v.text or "") if v is not None else ""
            if cell_type == "s" and raw.isdigit() and int(raw) < len(shared):
                value = shared[int(raw)]
            else:
                value = raw
            row_cells[col] = value
        if row_cells:
            max_col = max(row_cells)
            rows.append([row_cells.get(i, "") for i in range(max_col + 1)])
    return [r for r in rows if any(str(c).strip() for c in r)]


def _col_to_index(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n - 1


def _safe_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _get_cell(row: list[str], idx: int) -> str:
    return row[idx] if idx < len(row) else ""


def _deduplicate(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys([item for item in items if item]))
