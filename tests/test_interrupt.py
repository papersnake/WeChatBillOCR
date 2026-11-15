# -*- coding: utf-8 -*-
"""模拟第 2 屏发生 KeyboardInterrupt，验证已抓数据不丢失（P0 #1）"""
import json
import sys

sys.path.insert(0, r"E:\rou")
import wechat_bill_ocr as w

w.SCREEN_HEIGHT = 2736  # 样本截图来自 1264x2736 的屏幕；假截图没有 PNG 头，用此值算可视区

items = json.load(open(r"E:\rou\fixtures\sample_bill_items.json", encoding="utf-8"))

real_screenshot = w.screenshot
calls = {"n": 0}

def fake_screenshot():
    calls["n"] += 1
    if calls["n"] >= 2:
        raise KeyboardInterrupt  # 模拟第二屏时按 Ctrl+C
    return "bill_current.png"

def fake_ocr(path):
    return items

w.screenshot = fake_screenshot
w.ocr_image = fake_ocr
w.scroll_up = lambda: None
w.time.sleep = lambda *a: None

# 与 main() 完全相同的调用方式
records = []
try:
    w.collect_bills(all_records=records, max_scrolls=5)
except KeyboardInterrupt:
    print("用户中断，保留已抓取的数据...")

assert len(records) == 8, f"期望 8 条，实际 {len(records)}"
print(f"PASS: 中断后保留了 {len(records)} 条记录")
