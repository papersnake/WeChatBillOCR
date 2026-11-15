# -*- coding: utf-8 -*-
"""验证 P1：跨月归属、顶部残留条目、OCR 噪声去重、丢弃计数"""
import sys

sys.path.insert(0, r"E:\rou")
import wechat_bill_ocr as w


def mk(text, x, y, h=40, score=0.98):
    return {"text": text, "box": [[x, y], [x + 200, y], [x + 200, y + h], [x, y + h]], "score": score}


# 屏1：11月标题 + 11月1条，10月标题 + 10月2条
screen1 = [
    mk("2026年11月", 43, 480, 40),
    mk("如意馄饨", 245, 600), mk("11月4日20:51", 251, 655), mk("-21.80", 1047, 610),
    mk("2026年10月", 43, 800, 40),
    mk("兰州拉面", 245, 900), mk("10月30日15:34", 251, 955), mk("-18.00", 1047, 910),
    mk("萬鑫福面馆", 245, 1050), mk("10月30日09:11", 251, 1105), mk("-14.00", 1047, 1060),
]
# 屏2：顶部残留 10月条目（带 OCR 引号噪声）→ 应去重；新条目；1条无描述金额 → 应计数跳过
screen2 = [
    mk("兰州拉面”", 245, 200), mk("10月30日15:34", 251, 255), mk("-18.00", 1047, 210),
    mk("2026年10月", 43, 500, 40),
    mk("美团外卖", 245, 600), mk("10月28日12:00", 251, 655), mk("-25.50", 1047, 610),
    mk("-9.99", 1047, 1400),
]

screens = [screen1, screen2]
w.screenshot = lambda: "x.png"
w.ocr_image = lambda p: screens.pop(0) if screens else screen2
w.scroll_up = lambda: None
w.time.sleep = lambda *a: None

records = []
w.collect_bills(all_records=records, max_scrolls=2)

lines = [f"total={len(records)} (期望4)"]
for r in records:
    lines.append(f"{r['desc']} | {r['amount']:+.2f} | {r['time']} | {r['datetime']} | ym={r['year_month']}")

with open(r"E:\rou\output\_test_p1_out.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

assert len(records) == 4, f"期望 4 条（屏1的3条 + 屏2新增1条），实际 {len(records)}"
assert records[0]["datetime"] == "2026-11-04T20:51:00", "11月条目应归属 2026-11"
assert records[1]["datetime"] == "2026-10-30T15:34:00", "10月条目应归属 2026-10"
# 屏2顶部残留的噪声版本不应产生重复
descs = [r["desc"] for r in records]
assert "兰州拉面”" not in descs, "带噪声的重复记录不应出现"
print("PASS")
