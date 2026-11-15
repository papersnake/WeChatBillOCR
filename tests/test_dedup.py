# -*- coding: utf-8 -*-
"""跨屏去重回归测试：滚动重叠区的同一条账单不能重复记录。
可直接 `python tests/test_dedup.py` 或 `pytest tests/test_dedup.py` 运行，不依赖固定路径。"""
import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wechat_bill_ocr as w

SCREEN_H = 2736  # 与真实样本一致：可视区约 (492, 2712)


def mk(text, x, y, h=40, score=0.98):
    return {"text": text, "box": [[x, y], [x + 200, y], [x + 200, y + h], [x, y + h]], "score": score}


def row(desc, t, amt, y):
    """一条账单：描述和金额同高，时间在其下方 55px"""
    return [mk(desc, 245, y), mk(t, 251, y + 55), mk(amt, 1047, y + 10)]


def run(screens):
    """用给定的多屏 OCR 结果跑 collect_bills，返回 (records, 日志)"""
    saved = (w.screenshot, w.ocr_image, w.scroll_up, w.time.sleep, w.SCREEN_HEIGHT)
    queue = list(screens)
    w.SCREEN_HEIGHT = SCREEN_H
    w.screenshot = lambda: "no_such_file.png"  # 没有 PNG 头，可视区按 SCREEN_HEIGHT 算
    w.ocr_image = lambda p: queue.pop(0) if queue else screens[-1]
    w.scroll_up = lambda: None
    w.time.sleep = lambda *a: None
    records, buf = [], io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            w.collect_bills(all_records=records, max_scrolls=len(screens))
    finally:
        w.screenshot, w.ocr_image, w.scroll_up, w.time.sleep, w.SCREEN_HEIGHT = saved
    return records, buf.getvalue()


def test_degraded_desc_not_duplicated():
    """同一行在下一屏被读成“兰州拉”（描述少一个字）：时间+金额相同，不应重复"""
    s1 = [mk("2026年11月", 43, 480)] + row("兰州拉面", "11月3日20:57", "-18.00", 2000)
    s2 = (row("兰州拉", "11月3日20:57", "-18.00", 700)
          + row("美团外卖", "11月2日12:00", "-25.50", 1000))
    records, _ = run([s1, s2])
    assert [r["desc"] for r in records] == ["兰州拉面", "美团外卖"], records


def test_avatar_text_as_desc_not_duplicated():
    """描述被裁掉后，左侧商户头像里的文字（如“兰”）成了最近的描述候选：仍应并入原记录。
    注意“收”在 parse_records 里被当作固定界面文字过滤，不能用来测这个场景。"""
    s1 = [mk("2026年11月", 43, 480)] + row("兰州拉面", "11月3日20:57", "-18.00", 2000)
    s2 = row("兰", "11月3日20:57", "-18.00", 700) + row("美团外卖", "11月2日12:00", "-25.50", 1000)
    records, _ = run([s1, s2])
    assert [r["desc"] for r in records] == ["兰州拉面", "美团外卖"], records


def test_clipped_rows_are_dropped_by_view():
    """整行没有完整落在可视区内（贴顶/贴底）的条目不采用"""
    items = ([mk("2026年11月", 43, 560)]
             + row("贴顶", "11月5日09:18", "-10.00", 300)       # 行顶 300 < 492
             + row("正常", "11月4日20:51", "-21.80", 1000)
             + row("贴底", "11月1日07:36", "-2.00", 2680))      # 行底 2735 > 2712
    recs, _ = w.parse_records(items, view=(SCREEN_H * w.LIST_TOP_RATIO, SCREEN_H - w.EDGE_BOTTOM_PX))
    assert [r["desc"] for r in recs] == ["正常"], recs
    recs_no_view, _ = w.parse_records(items)  # 不传 view 则不过滤（保持旧行为）
    assert len(recs_no_view) == 3


def test_identical_rows_in_same_minute_are_kept():
    """同一分钟内两笔相同金额的真实账单都要保留，且下一屏重叠时不重复"""
    r1 = row("智慧停车场", "11月1日07:36", "-2.00", 1000)
    r2 = row("智慧停车场", "11月1日07:36", "-2.00", 1250)
    s1 = [mk("2026年11月", 43, 480)] + r1 + r2
    s2 = (row("智慧停车场", "11月1日07:36", "-2.00", 700)
          + row("智慧停车场", "11月1日07:36", "-2.00", 950)
          + row("美团外卖", "10月31日12:00", "-25.50", 1200))
    records, _ = run([s1, s2])
    assert [r["desc"] for r in records] == ["智慧停车场", "智慧停车场", "美团外卖"], records


def test_year_boundary_residual_row():
    """1 月条目残留在屏顶、12 月标题在其下方：年份应为 2027，且不与上一屏重复"""
    s1 = ([mk("2027年1月", 43, 480)] + row("兰州拉面", "1月3日20:51", "-18.00", 600)
          + [mk("2026年12月", 43, 1000)] + row("美团外卖", "12月30日12:00", "-25.50", 1100))
    s2 = (row("兰州拉面", "1月3日20:51", "-18.00", 700)
          + [mk("2026年12月", 43, 900)] + row("美团外卖", "12月30日12:00", "-25.50", 1000))
    records, _ = run([s1, s2])
    assert sorted(r["datetime"] for r in records) == ["2026-12-30T12:00:00", "2027-01-03T20:51:00"], records


def test_warn_when_no_overlap():
    """两屏之间完全没有重叠时给出警告（可能漏记）"""
    s1 = [mk("2026年11月", 43, 480)] + row("兰州拉面", "11月3日20:57", "-18.00", 2000)
    s2 = row("美团外卖", "11月2日12:00", "-25.50", 1000)
    records, log = run([s1, s2])
    assert len(records) == 2
    assert "没有任何重叠" in log


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
