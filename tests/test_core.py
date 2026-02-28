import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from src.services.excel_parser import parse_keywords_excel, parse_posts_excel
from src.services.llm_analyzer import QwenAnalyzer
from src.storage.keyword_store import KeywordStore


def build_xlsx(rows):
    shared = []
    def sidx(val):
        if val not in shared:
            shared.append(val)
        return shared.index(val)

    sheet_rows = []
    for r_idx, row in enumerate(rows, start=1):
        cells = []
        for c_idx, val in enumerate(row):
            col = chr(ord('A') + c_idx)
            idx = sidx(str(val))
            cells.append(f'<c r="{col}{r_idx}" t="s"><v>{idx}</v></c>')
        sheet_rows.append(f"<row r=\"{r_idx}\">{''.join(cells)}</row>")

    shared_xml = "".join([f"<si><t>{v}</t></si>" for v in shared])
    sheet_xml = f"""<?xml version='1.0' encoding='UTF-8'?>
<worksheet xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'>
<sheetData>{''.join(sheet_rows)}</sheetData>
</worksheet>"""

    content_types = """<?xml version='1.0' encoding='UTF-8'?>
<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>
  <Override PartName='/xl/worksheets/sheet1.xml' ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml'/>
  <Override PartName='/xl/sharedStrings.xml' ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml'/>
</Types>"""

    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w') as z:
        z.writestr('[Content_Types].xml', content_types)
        z.writestr('xl/worksheets/sheet1.xml', sheet_xml)
        z.writestr('xl/sharedStrings.xml', f"<sst xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'>{shared_xml}</sst>")
    return b.getvalue()


class CoreTests(unittest.TestCase):
    def test_parse_posts_csv(self):
        data = 'title,content\n穿搭1,高级感\n,\n'.encode()
        rows = parse_posts_excel(data)
        self.assertEqual(rows[0]['title'], '穿搭1')

    def test_parse_keywords_xlsx(self):
        binary = build_xlsx([["keyword"], ["通勤"], ["通勤"], ["极简"]])
        kws = parse_keywords_excel(binary)
        self.assertEqual(kws, ["通勤", "极简"])

    def test_keyword_store(self):
        with tempfile.TemporaryDirectory() as d:
            store = KeywordStore(Path(d) / 'k.json')
            store.add_manual_keyword('A')
            store.replace_excel_keywords(['B', 'A'])
            payload = store.get_all()
            self.assertEqual(payload['active_keywords'], ['A', 'B'])

    def test_analyzer(self):
        az = QwenAnalyzer()
        out = az.analyze_posts([{'title': '通勤穿搭', 'content': '通勤也要高级'}], ['通勤'])
        self.assertEqual(out['summary']['total_mentions'], 2)


if __name__ == '__main__':
    unittest.main()
