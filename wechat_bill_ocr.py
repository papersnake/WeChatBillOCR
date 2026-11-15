#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信账单自动截图识别统计工具

前置条件：
  1. 手机已通过 adb 无线/有线连接电脑
  2. Umi-OCR 已启动，HTTP API 监听 127.0.0.1:1224
  3. 用户已将微信账单页面滚动到最顶部

脚本流程：
  循环截图 → OCR 识别 → 解析账单条目 → 向上滚动 → 直到没有新记录
"""

import argparse
import base64
import csv
import json
import os
import re
import statistics
import subprocess
import sys
import time
import urllib.request
from collections import defaultdict, deque
from datetime import datetime, date

# ==================== 配置 ====================
ADB_PATH = r"E:\rou\scrcpy\scrcpy-win64-v3.2\adb.exe"
UMI_OCR_URL = "http://127.0.0.1:1224/api/ocr"

# 输出目录（脚本所在目录下的 output\，截图与统计结果都写这里）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
SHOT_FILE = os.path.join(OUTPUT_DIR, "bill_current.png")
# 输出文件名时间戳
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# 运行时动态获取
DEVICE = None
SCREEN_WIDTH = 1080
SCREEN_HEIGHT = 2400

# 列表可视区：上沿 = 屏高 × LIST_TOP_RATIO（固定头部之下），下沿 = 屏高 - EDGE_BOTTOM_PX。
# 整行没有完整落在可视区内的条目（被上/下边缘裁切）OCR 经常读坏，直接不采用，
# 等它在下一屏完整出现时再记录。
LIST_TOP_RATIO = 0.18
EDGE_BOTTOM_PX = 24


# ==================== 命令行参数 ====================
def parse_args():
    parser = argparse.ArgumentParser(description="微信账单自动截图识别统计")
    parser.add_argument("--device", type=str, help="指定 adb 设备，如 192.168.1.100:5555")
    parser.add_argument("--start-date", type=str, help="开始日期，格式 2024-01-01")
    parser.add_argument("--end-date", type=str, help="结束日期，格式 2024-12-31")
    parser.add_argument("--months", type=int, help="统计最近 N 个月（与日期参数互斥）")
    parser.add_argument("--max-scrolls", type=int, default=100, help="最大滚动次数")
    return parser.parse_args()


def parse_date(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"无法解析日期：{s}")


# ==================== adb 操作 ====================
def run_adb(args):
    """执行 adb 命令"""
    cmd = [ADB_PATH]
    if DEVICE:
        cmd.extend(["-s", DEVICE])
    cmd.extend(args)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        timeout=30,
    )
    return result


def list_devices():
    """获取当前已连接的 adb 设备列表"""
    result = run_adb(["devices", "-l"])
    devices = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices


def select_device(preferred=None):
    """选择 adb 设备"""
    global DEVICE
    devices = list_devices()
    if not devices:
        print("错误：没有检测到任何 adb 设备")
        print("请确认手机已开启 USB 调试或无线调试已连接")
        return False

    if preferred and preferred in devices:
        DEVICE = preferred
    elif len(devices) == 1:
        DEVICE = devices[0]
    else:
        print("检测到多个设备：")
        for idx, d in enumerate(devices, 1):
            print(f"  {idx}. {d}")
        # 非交互环境默认选第一个
        DEVICE = devices[0]
        print(f"自动选择第一个设备：{DEVICE}")
        print("如需指定其他设备，请使用 --device 参数")

    print(f"设备已连接：{DEVICE}")
    return True


def get_screen_size():
    """自动获取手机屏幕分辨率"""
    global SCREEN_WIDTH, SCREEN_HEIGHT
    result = run_adb(["shell", "wm", "size"])
    # 输出类似：Physical size: 1264x2736
    m = re.search(r"(\d+)x(\d+)", result.stdout)
    if m:
        SCREEN_WIDTH = int(m.group(1))
        SCREEN_HEIGHT = int(m.group(2))
        print(f"屏幕分辨率：{SCREEN_WIDTH}x{SCREEN_HEIGHT}")
    else:
        print(f"无法自动获取分辨率，使用默认值 {SCREEN_WIDTH}x{SCREEN_HEIGHT}")


def check_device():
    """检查设备是否连接"""
    devices = list_devices()
    global DEVICE
    if DEVICE and DEVICE in devices:
        print(f"设备已连接：{DEVICE}")
        return True
    print(f"错误：未找到设备 {DEVICE}")
    print("当前设备列表：")
    for d in devices:
        print(f"  {d}")
    return False


def screenshot():
    """截图并保存为 PNG，返回文件路径"""
    cmd = [
        ADB_PATH,
        "-s",
        DEVICE,
        "exec-out",
        "screencap",
        "-p",
    ]
    with open(SHOT_FILE, "wb") as f:
        subprocess.run(cmd, stdout=f, timeout=30)
    return SHOT_FILE


def png_size(path):
    """读 PNG 头部得到截图真实 (宽, 高)；读不到返回 None。
    不能只信 wm size：有 Override size 时它和截图尺寸不一致。"""
    try:
        with open(path, "rb") as f:
            head = f.read(24)
    except OSError:
        return None
    if head[:8] != b"\x89PNG\r\n\x1a\n" or len(head) < 24:
        return None
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def scroll_up():
    """向上滚动一屏"""
    x = SCREEN_WIDTH // 2
    y_start = int(SCREEN_HEIGHT * 0.72)
    y_end = int(SCREEN_HEIGHT * 0.32)
    duration = 350
    run_adb(["shell", "input", "swipe", str(x), str(y_start), str(x), str(y_end), str(duration)])


# ==================== OCR 调用 ====================
def ocr_image(path):
    """调用 Umi-OCR HTTP API 识别图片，返回 [{text, box, score}]"""
    with open(path, "rb") as f:
        img_bytes = f.read()
    b64 = base64.b64encode(img_bytes).decode()
    payload = json.dumps({"base64": b64}).encode("utf-8")
    req = urllib.request.Request(
        UMI_OCR_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"OCR 请求失败：{e}")
        return []

    if result.get("code") != 100:
        print(f"OCR 返回错误：{result}")
        return []

    items = []
    for r in result.get("data", []):
        items.append({
            "text": r.get("text", "").strip(),
            "box": r.get("box", []),
            "score": r.get("score", 0),
        })
    return items


# ==================== 文本块几何信息 ====================
def block_center_y(box):
    """取文本块 4 个角点的 y 平均值"""
    if not box or len(box) < 4:
        return 0
    return statistics.mean(p[1] for p in box[:4])


def block_center_x(box):
    """取文本块 4 个角点的 x 平均值"""
    if not box or len(box) < 4:
        return 0
    return statistics.mean(p[0] for p in box[:4])


def block_height(box):
    """文本块高度"""
    if not box or len(box) < 4:
        return 0
    ys = [p[1] for p in box[:4]]
    return max(ys) - min(ys)


# ==================== 账单解析 ====================
AMOUNT_RE = re.compile(r"^[+-]?\d{1,6}\.\d{2}$")
TIME_RE = re.compile(r"(\d{1,2}月\d{1,2}日)\s*(\d{1,2}:\d{2})")
MONTH_TITLE_RE = re.compile(r"(\d{4})年(\d{1,2})月")


def is_amount(text):
    return bool(AMOUNT_RE.match(text.replace(",", "")))


def normalize_desc(text):
    """描述归一化：去掉空白和 OCR 常读出的引号/标点噪声（如 '如意馄饨”'），
    相邻屏同一条账单才能在去重时命中同一条记录。"""
    return re.sub(r"[\s\"'“”‘’「」『』《》·。]", "", text)


def is_time(text):
    return bool(TIME_RE.search(text))


def parse_month_title(text):
    m = MONTH_TITLE_RE.search(text)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def parse_time(text, year, month):
    """把 '11月3日20:57' 转为 datetime"""
    m = TIME_RE.search(text)
    if not m or not year or not month:
        return None
    date_part = m.group(1)  # 11月3日
    time_part = m.group(2)  # 20:57
    try:
        dt = datetime.strptime(f"{year}年{date_part}{time_part}", "%Y年%m月%d日%H:%M")
        return dt
    except ValueError:
        return None


def resolve_year(ref_year, ref_month, time_text):
    """条目年份 = 参考标题年月附近、与条目自身月份最接近的那一年。
    跨年时 1 月的条目会排在 12 月标题上方（或作为残留出现在下一屏顶部），
    不能直接套用标题年份。"""
    m = TIME_RE.search(time_text)
    if not m or not ref_year or not ref_month:
        return ref_year
    item_month = int(m.group(1).split("月")[0])
    return min((ref_year - 1, ref_year, ref_year + 1),
               key=lambda y: abs((y * 12 + item_month) - (ref_year * 12 + ref_month)))


def parse_records(items, current_year_month=None, view=None):
    """从 OCR 结果中解析账单记录，返回 (records, detected_year_month)。
    view=(top, bottom) 给出列表可视区纵坐标；整行没有完整落在其中的条目
    （被屏幕上/下边缘裁切，OCR 容易读坏）会被丢弃。view=None 则不做此过滤。"""
    records = []
    detected_year_month = current_year_month

    # 过滤掉低置信度和页面固定 UI
    filtered = []
    for it in items:
        text = it["text"]
        score = it.get("score", 0)
        if score < 0.3:
            continue
        if text in ("X", "全部账单", "账单", "查找交易", "收支统计>", "收"):
            continue
        if "支出¥" in text or "收入¥" in text:
            continue
        if text.startswith("Q"):
            continue
        filtered.append(it)

    # 上一屏最后一个（最旧）标题：本屏完全没有标题时，条目沿用它。
    # 必须在下面更新 detected_year_month 之前取值。
    carry_over = current_year_month

    # 收集月份标题及其 y 坐标。detected_year_month 取本屏最靠下（最旧）的标题，
    # 交给下一屏兜底；按 y 排序，不依赖 OCR 返回顺序。
    titles = []
    for it in filtered:
        y, m = parse_month_title(it["text"])
        if y and m:
            titles.append((block_center_y(it["box"]), (y, m)))
            print(f"  [月份标题] {y}年{m}月")
    titles.sort()
    if titles:
        detected_year_month = titles[-1][1]

    def month_for(y_pos):
        """年月参考标题：条目上方最近的标题（月份标题在条目组上方）；
        屏顶残留条目上方没有标题，改用其下方最近的标题；本屏无标题则沿用上一屏。
        这只是参考，条目的真实年份由 resolve_year 结合条目自己的月份推断。"""
        above = [t for t in titles if t[0] < y_pos]
        if above:
            return above[-1][1]
        if titles:
            return titles[0][1]
        return carry_over or (None, None)

    # 按 y 坐标分组（同一账单条目在同一水平区域）
    amount_items = [it for it in filtered if is_amount(it["text"])]
    other_items = [it for it in filtered if not is_amount(it["text"])]

    for amt_it in amount_items:
        amt_y = block_center_y(amt_it["box"])
        amt_x = block_center_x(amt_it["box"])
        raw_amt = amt_it["text"].strip().replace(",", "")
        amount = float(raw_amt)

        # 找同一水平线附近的描述和时间
        desc_candidates = []
        time_candidates = []
        for oit in other_items:
            oy = block_center_y(oit["box"])
            ox = block_center_x(oit["box"])
            h = block_height(amt_it["box"])
            if abs(oy - amt_y) < max(h * 2.5, 80):
                if ox < amt_x - 50:  # 在金额左侧
                    if is_time(oit["text"]):
                        time_candidates.append(oit)
                    else:
                        desc_candidates.append(oit)

        # 选择最靠近金额的描述和时间
        desc = ""
        if desc_candidates:
            desc_candidates.sort(key=lambda x: abs(block_center_y(x["box"]) - amt_y))
            desc = desc_candidates[0]["text"]

        time_str = ""
        dt = None
        e_year, e_month = month_for(amt_y)
        if time_candidates:
            time_candidates.sort(key=lambda x: abs(block_center_y(x["box"]) - amt_y))
            time_str = time_candidates[0]["text"]
            dt = parse_time(time_str, resolve_year(e_year, e_month, time_str), e_month)

        # 整行（描述/金额/时间）必须完整落在可视区内，否则视为被裁切，等下一屏再记
        if view:
            row_boxes = [amt_it["box"]]
            if desc_candidates:
                row_boxes.append(desc_candidates[0]["box"])
            if time_candidates:
                row_boxes.append(time_candidates[0]["box"])
            row_top = min(p[1] for b in row_boxes for p in b[:4])
            row_bottom = max(p[1] for b in row_boxes for p in b[:4])
            if row_top < view[0] or row_bottom > view[1]:
                print(f"  [贴边丢弃] {desc} | {raw_amt} | {time_str}")
                continue

        # 符号规则：OCR 读出的 +/- 最可信，优先信任；
        # 无符号时按描述判断：收入描述集合有限（退款/收款/红包等），
        # 其余一律默认支出——OCR 常丢符号，漏判支出会把美团/京东等
        # 商户误记成收入，导致收入虚高。
        income_kw = ["退款", "收款", "入账", "红包", "工资", "来自"]
        if raw_amt.startswith("-"):
            amount = -abs(amount)
        elif raw_amt.startswith("+"):
            amount = abs(amount)
        elif desc and any(k in desc for k in income_kw):
            amount = abs(amount)
        else:
            amount = -abs(amount)

        records.append({
            "desc": desc,
            "amount": amount,
            "time": time_str,
            "datetime": dt.isoformat() if dt else "",
            "year_month": (e_year, e_month),
        })

    return records, detected_year_month


# ==================== 跨屏去重 ====================
def _when(r):
    """时间（月日+时分），与年份推断无关，OCR 对数字也最稳定"""
    m = TIME_RE.search(r["time"])
    return (m.group(1), m.group(2)) if m else normalize_desc(r["time"])


def same_record(a, b):
    """同一条账单：时间精确到分钟、金额绝对值都相同。
    描述不参与判定——被屏幕边缘裁切的行，描述最容易被读少一个字或读成头像文字。"""
    return _when(a) == _when(b) and abs(abs(a["amount"]) - abs(b["amount"])) < 0.005


def match_overlap(cur, pool):
    """把本屏记录 cur 与已记录的 pool 一一配对，返回与 cur 等长的列表，
    配上的元素是 pool 里的那条记录，没配上的是 None（即新记录）。
    每条 pool 记录至多被消耗一次，所以同一分钟内两笔相同金额的真实账单不会被误合并。
    先配描述也相同的，再配仅时间+金额相同的。"""
    pairs = [None] * len(cur)
    used = set()
    for need_same_desc in (True, False):
        for i, r in enumerate(cur):
            if pairs[i] is not None:
                continue
            for j, p in enumerate(pool):
                if j in used or not same_record(r, p):
                    continue
                if need_same_desc and normalize_desc(r["desc"]) != normalize_desc(p["desc"]):
                    continue
                pairs[i] = p
                used.add(j)
                break
    return pairs


# ==================== 主流程 ====================
def collect_bills(start_date=None, end_date=None, max_scrolls=100, all_records=None):
    """循环截图 OCR 抓取账单。all_records 可由外部传入，中断时已抓数据不丢"""
    if all_records is None:
        all_records = []
    recent_screens = deque(maxlen=2)  # 最近两屏的记录，去重时作为配对池
    no_new_count = 0
    skipped_no_parse = 0
    current_year_month = None

    print("开始抓取微信账单...")
    print("请确保账单页面已滚动到最顶部")
    if start_date:
        print(f"开始日期：{start_date}")
    if end_date:
        print(f"结束日期：{end_date}")
    time.sleep(2)

    for i in range(max_scrolls):
        print(f"\n--- 第 {i + 1} 屏 ---")
        path = screenshot()
        items = ocr_image(path)
        if not items:
            print("OCR 未识别到内容，跳过")
            continue

        size = png_size(path)
        screen_h = size[1] if size else SCREEN_HEIGHT
        view = (screen_h * LIST_TOP_RATIO, screen_h - EDGE_BOTTOM_PX)
        records, current_year_month = parse_records(items, current_year_month, view=view)
        new_count = 0
        early_stop = False
        screen_records = []  # 本屏通过日期过滤、描述和时间都配对成功的记录

        for r in records:
            # 日期范围过滤
            if r["datetime"]:
                try:
                    r_date = datetime.fromisoformat(r["datetime"]).date()
                    if start_date and r_date < start_date:
                        print(f"  [超出开始日期] {r['desc']} {r['time']}，停止抓取")
                        early_stop = True
                        continue
                    if end_date and r_date > end_date:
                        continue
                except Exception:
                    pass

            if not (r["desc"] and r["time"]):
                # 描述或时间没配对上，无法去重也无法过滤日期，跳过并计数
                skipped_no_parse += 1
                continue
            screen_records.append(r)

        # 与最近两屏的记录配对：配上的是滚动重叠区里的同一条账单，没配上的才是新增
        pool = list({id(p): p for prev in recent_screens for p in prev}.values())
        pairs = match_overlap(screen_records, pool)
        if pool and screen_records and all(p is None for p in pairs):
            print("  [警告] 本屏与前两屏没有任何重叠，滚动距离可能过大，两屏之间可能漏记条目")
        kept = []
        for r, p in zip(screen_records, pairs):
            if p is None:
                all_records.append(r)
                kept.append(r)
                new_count += 1
                print(f"  + {r['desc']} | {r['amount']:.2f} | {r['time']}")
            else:
                kept.append(p)
        if kept:
            recent_screens.append(kept)

        print(f"本屏新增 {new_count} 条，累计 {len(all_records)} 条")

        if early_stop:
            print("已超出指定日期范围，停止")
            break

        # 根据日期范围提前停止：如果当前月份早于开始月份，停止
        if start_date and current_year_month:
            cy, cm = current_year_month
            # 当前识别的月份是否比 start_date 早
            current_month_date = date(cy, cm, 1)
            if current_month_date < date(start_date.year, start_date.month, 1):
                print("当前月份已早于开始日期范围，停止")
                break

        # 判断是否到底
        if new_count == 0:
            no_new_count += 1
            if no_new_count >= 2:
                print("连续两屏无新记录，已到达底部")
                break
        else:
            no_new_count = 0

        scroll_up()
        time.sleep(1.2)

    if skipped_no_parse:
        print(f"\n注意：{skipped_no_parse} 条金额因描述/时间未识别成功被跳过，建议人工核对")

    return all_records


def summarize(records):
    """汇总统计"""
    income = [r for r in records if r["amount"] > 0]
    expense = [r for r in records if r["amount"] < 0]

    total_income = sum(r["amount"] for r in income)
    total_expense = sum(r["amount"] for r in expense)

    # 按描述汇总支出
    desc_summary = defaultdict(lambda: {"count": 0, "amount": 0.0})
    for r in expense:
        desc_summary[r["desc"]]["count"] += 1
        desc_summary[r["desc"]]["amount"] += r["amount"]

    print("\n========== 账单统计结果 ==========")
    print(f"总记录数：{len(records)}")
    print(f"收入：{len(income)} 笔，共 {total_income:+.2f}")
    print(f"支出：{len(expense)} 笔，共 {total_expense:+.2f}")
    print(f"净额：{total_income + total_expense:+.2f}")

    if expense:
        print("\n--- 支出 TOP ---")
        for desc, info in sorted(desc_summary.items(), key=lambda x: x[1]["amount"])[:20]:
            print(f"{desc}: {info['count']}笔, 共 {info['amount']:.2f}")

    return {
        "total": len(records),
        "income_count": len(income),
        "total_income": total_income,
        "expense_count": len(expense),
        "total_expense": total_expense,
        "net": total_income + total_expense,
    }


def save_results(records, summary):
    """保存为 JSON 和 CSV"""
    json_file = os.path.join(OUTPUT_DIR, f"wechat_bills_ocr_{TIMESTAMP}.json")
    csv_file = os.path.join(OUTPUT_DIR, f"wechat_bills_ocr_{TIMESTAMP}.csv")

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump({"records": records, "summary": summary}, f, ensure_ascii=False, indent=2)

    with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["描述", "金额", "时间"])
        for r in records:
            writer.writerow([r["desc"], f"{r['amount']:.2f}", r["time"]])

    print(f"\n结果已保存：{json_file}、{csv_file}")


def main():
    args = parse_args()

    start_date = parse_date(args.start_date) if args.start_date else None
    end_date = parse_date(args.end_date) if args.end_date else None

    if args.months:
        # 最近 N 个月
        today = date.today()
        # 从当前月往前推 N-1 个月
        month = today.month - (args.months - 1)
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        start_date = date(year, month, 1)
        end_date = today
        print(f"统计最近 {args.months} 个月：{start_date} 至 {end_date}")

    # 自动选择/检测设备
    if not select_device(args.device):
        return

    # 自动获取屏幕分辨率
    get_screen_size()

    print("\n请确保：")
    print("  1. Umi-OCR 已启动（黑色小图标在任务栏）")
    print("  2. 微信账单页面已滚动到最顶部")
    print("  3. 手机保持亮屏")
    for i in range(5, 0, -1):
        print(f"  {i} 秒后开始...")
        time.sleep(1)

    records = []
    try:
        collect_bills(
            start_date=start_date,
            end_date=end_date,
            max_scrolls=args.max_scrolls,
            all_records=records,
        )
    except KeyboardInterrupt:
        print("\n用户中断，保留已抓取的数据...")

    if not records:
        print("未抓取到任何记录，请检查页面是否已打开")
        return

    summary = summarize(records)
    save_results(records, summary)


if __name__ == "__main__":
    main()
