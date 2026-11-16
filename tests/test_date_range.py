# -*- coding: utf-8 -*-
"""--today / --days / --months 的日期范围计算。可直接 python tests/test_date_range.py 运行。"""
import os
import sys
from argparse import Namespace
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wechat_bill_ocr as w

TODAY = date(2026, 11, 16)


def ns(**kw):
    base = dict(today=False, days=None, months=None, start_date=None, end_date=None)
    base.update(kw)
    return Namespace(**base)


def test_today_is_single_day():
    assert w.resolve_date_range(ns(today=True), TODAY) == (TODAY, TODAY)


def test_days_includes_today():
    assert w.resolve_date_range(ns(days=1), TODAY) == (TODAY, TODAY)
    assert w.resolve_date_range(ns(days=7), TODAY) == (date(2026, 11, 10), TODAY)


def test_days_crosses_month_and_year():
    assert w.resolve_date_range(ns(days=20), TODAY) == (date(2026, 10, 28), TODAY)
    assert w.resolve_date_range(ns(days=3), date(2027, 1, 1)) == (date(2026, 12, 30), date(2027, 1, 1))


def test_months_unchanged():
    assert w.resolve_date_range(ns(months=2), TODAY) == (date(2026, 10, 1), TODAY)
    assert w.resolve_date_range(ns(months=12), TODAY) == (date(2025, 12, 1), TODAY)


def test_explicit_dates_unchanged():
    assert w.resolve_date_range(ns(start_date="2024-01-01", end_date="2024-12-31"), TODAY) == \
        (date(2024, 1, 1), date(2024, 12, 31))
    assert w.resolve_date_range(ns(), TODAY) == (None, None)


def test_conflicting_or_invalid_options_rejected():
    for bad in (ns(today=True, months=2), ns(days=3, start_date="2026-11-01"), ns(days=0), ns(days=-2)):
        try:
            w.resolve_date_range(bad, TODAY)
        except ValueError:
            continue
        raise AssertionError(f"应当拒绝：{bad}")


if __name__ == "__main__":
    for t in [v for k, v in sorted(globals().items()) if k.startswith("test_")]:
        t()
        print("PASS", t.__name__)
