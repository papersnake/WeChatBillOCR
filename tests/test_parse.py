# -*- coding: utf-8 -*-
"""用 fixtures/sample_bill_items.json 里的真实 OCR 结果验证 parse_records"""
import json
import sys

sys.path.insert(0, r"E:\rou")
import wechat_bill_ocr as w

items = json.load(open(r"E:\rou\fixtures\sample_bill_items.json", encoding="utf-8"))
recs, ym = w.parse_records(items)

lines = [f"detected year_month={ym}", f"record count={len(recs)}"]
for r in recs:
    lines.append(f"{r['desc']} | {r['amount']:+.2f} | {r['time']} | {r['datetime']}")

with open(r"E:\rou\output\_debug_parse.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("ok")
