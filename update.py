import json
import os
import re
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path


CST = timezone(timedelta(hours=8))
DATA_FILE = Path("data.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
}


def log(message):
    print(message, flush=True)


def normalize_record(expect, open_code, open_time):
    nums = [int(x) for x in re.findall(r"\d", str(open_code))]
    if len(nums) != 3:
        return None

    date_match = re.search(r"\d{4}-\d{2}-\d{2}", str(open_time))
    open_date = date_match.group(0) if date_match else ""
    return {
        "expect": str(expect),
        "opencode": ",".join(str(n) for n in nums),
        "opentime": open_date,
    }


def get_text(url, params):
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(f"{url}?{query}", headers=HEADERS)
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read()
        charset = response.headers.get_content_charset()

    for encoding in [charset, "utf-8", "gb18030", "gbk"]:
        if not encoding:
            continue
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def get_json(url, params):
    body = get_text(url, params)
    return json.loads(body)


def fetch_from_mxnzp(size=50):
    app_id = os.environ.get("MXNZP_APP_ID", "").strip()
    app_secret = os.environ.get("MXNZP_APP_SECRET", "").strip()
    if not app_id or not app_secret:
        log("MXNZP secrets are not configured, skipping MXNZP.")
        return []

    url = "https://www.mxnzp.com/api/lottery/common/history"
    params = {
        "code": "fc3d",
        "size": size,
        "app_id": app_id,
        "app_secret": app_secret,
    }
    payload = get_json(url, params)
    if payload.get("code") != 1:
        raise RuntimeError(payload.get("msg") or "MXNZP returned an error")

    records = []
    for item in payload.get("data", []):
        record = normalize_record(item.get("expect"), item.get("openCode"), item.get("time"))
        if record:
            records.append(record)
    return records


def fetch_history(size=50):
    sources = (
        ("mxnzp.com", fetch_from_mxnzp),
    )
    for name, fetcher in sources:
        try:
            records = fetcher(size)
            records = sorted(records, key=lambda x: x["expect"], reverse=True)
            if records:
                log(f"Fetched {len(records)} records from {name}.")
                return records
        except Exception as exc:
            log(f"Fetch failed from {name}: {exc}")
    return []


def mark_update_failed(now):
    old = {}
    if DATA_FILE.exists():
        try:
            old = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            old = {}
    old["update_failed"] = True
    old["failed_time"] = now.strftime("%Y-%m-%d %H:%M")
    old["error"] = "数据源暂时不可用，已保留上次成功更新的数据。"
    DATA_FILE.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_nums(item):
    return [int(x) for x in item["opencode"].split(",")]


def unique_n(values, n):
    seen = []
    for value in values:
        if value not in seen:
            seen.append(value)
        if len(seen) == n:
            break
    return sorted(seen[:n])


def draw_type(nums):
    unique_count = len(set(nums))
    if unique_count == 1:
        return "豹子"
    if unique_count == 2:
        return "组三"
    return "组六"


def analyze(records):
    all_flat = []
    all_recs = []
    for item in records[:30]:
        nums = parse_nums(item)
        all_flat.extend(nums)
        all_recs.append(nums)

    count = Counter(all_flat)
    sorted_freq = sorted(count.items(), key=lambda x: (-x[1], x[0]))
    hot = [n for n, _ in sorted_freq[:5]]
    cold = [n for n, _ in sorted(count.items(), key=lambda x: (x[1], x[0]))[:4]]

    miss = {}
    for digit in range(10):
        miss[digit] = 0
        for rec in all_recs:
            if digit in rec:
                break
            miss[digit] += 1

    high_miss = sorted([d for d, m in miss.items() if m >= 3], key=lambda d: (-miss[d], d))

    road_counts = [0, 0, 0]
    for item in records[:10]:
        for num in parse_nums(item):
            road_counts[num % 3] += 1
    min_road = road_counts.index(min(road_counts))
    road_digits = {0: [0, 3, 6, 9], 1: [1, 4, 7], 2: [2, 5, 8]}

    dan1 = high_miss[0] if high_miss else hot[0]
    dan2 = unique_n(([high_miss[0]] if high_miss else []) + hot + list(range(10)), 2)
    dan3 = unique_n(hot[:3] + high_miss[:2] + road_digits[min_road] + list(range(10)), 3)
    code5 = unique_n(hot[:3] + high_miss[:3] + cold + list(range(10)), 5)

    return {
        "dan1": dan1,
        "dan2": dan2,
        "dan3": dan3,
        "code5": code5,
        "miss": miss,
        "hot": hot,
        "cold": cold,
    }


def build_backtest(records):
    details = []
    total = h1 = h2 = h3 = h5 = 0
    max_bt = min(len(records) - 30, 20)
    for i in range(max_bt):
        target = records[i]
        history = records[i + 1 : i + 31]
        if len(history) < 10:
            continue
        rec = analyze(history)
        actual = parse_nums(target)
        d1 = rec["dan1"] in actual
        d2 = any(d in actual for d in rec["dan2"])
        d3 = any(d in actual for d in rec["dan3"])
        c5 = all(n in rec["code5"] for n in actual)

        total += 1
        h1 += int(d1)
        h2 += int(d2)
        h3 += int(d3)
        h5 += int(c5)
        details.append(
            {
                "period": target["expect"],
                "date": target["opentime"],
                "actual": actual,
                "dan1": rec["dan1"],
                "dan2": rec["dan2"],
                "dan3": rec["dan3"],
                "code5": rec["code5"],
                "dan1_hit": d1,
                "dan2_hit": d2,
                "dan3_hit": d3,
                "code5_hit": c5,
            }
        )

    def pct(value):
        return round(value / total * 100, 1) if total else 0

    return {
        "summary": {
            "total": total,
            "dan1": {"hit": h1, "rate": pct(h1), "random_rate": 30.0},
            "dan2": {"hit": h2, "rate": pct(h2), "random_rate": 51.2},
            "dan3": {"hit": h3, "rate": pct(h3), "random_rate": 65.7},
            "code5": {"hit": h5, "rate": pct(h5), "random_rate": 8.3},
        },
        "details": details[:20],
    }


def pick_combos(pool, dan1, count=3):
    combos = []
    pool = sorted(set(pool))
    for i in range(len(pool)):
        for j in range(i, len(pool)):
            for k in range(j, len(pool)):
                combo = [pool[i], pool[j], pool[k]]
                if dan1 in combo:
                    combos.append(combo)
                if len(combos) >= count:
                    return combos
    return combos


def build_output(records, now):
    latest_item = records[0]
    latest_nums = parse_nums(latest_item)

    history = []
    for item in records[:10]:
        nums = parse_nums(item)
        history.append(
            {
                "period": item["expect"],
                "date": item["opentime"],
                "numbers": nums,
                "type": draw_type(nums),
                "sum": sum(nums),
                "span": max(nums) - min(nums),
            }
        )

    today_rec = analyze(records[1:31] if len(records) > 31 else records[1:])
    hot_nums = today_rec["hot"]
    cold_nums = today_rec["cold"]
    miss = today_rec["miss"]
    high_miss = sorted([d for d, m in miss.items() if m >= 3], key=lambda d: (-miss[d], d))

    road_counts = [0, 0, 0]
    for item in records[:10]:
        for n in parse_nums(item):
            road_counts[n % 3] += 1
    total_road = sum(road_counts) or 1
    road_ratio = [round(c / total_road * 100) for c in road_counts]
    min_road = road_counts.index(min(road_counts))
    road_digits = {0: [0, 3, 6, 9], 1: [1, 4, 7], 2: [2, 5, 8]}

    sums = [sum(parse_nums(item)) for item in records[:10]]
    avg_sum = round(sum(sums) / len(sums), 1) if sums else 0
    if avg_sum < 10:
        sum_range = "中大和值（10-18）"
    elif avg_sum > 18:
        sum_range = "中小和值（8-16）"
    else:
        sum_range = "中和值（10-18）"

    odd_counts = sum(1 for item in records[:10] for n in parse_nums(item) if n % 2 == 1)
    parity_tip = "近期奇码偏多，建议搭配偶码。" if odd_counts > 15 else "近期偶码偏多，建议搭配奇码。"

    analysis_text = (
        f"近30期热码为 {hot_nums[:4]}，冷码为 {cold_nums[:3]}。"
        f"高遗漏号码为 {high_miss[:3] if high_miss else '暂无'}。"
        f"近10期和值均值 {avg_sum}，建议关注{sum_range}。"
        f"012路分布：0路{road_ratio[0]}%，1路{road_ratio[1]}%，2路{road_ratio[2]}%，"
        f"{min_road}路偏少，可适当补充{road_digits[min_road][:3]}。"
        f"{parity_tip}"
    )

    combos = pick_combos(today_rec["code5"], today_rec["dan1"], 3)

    return {
        "period": latest_item["expect"],
        "date": latest_item["opentime"] or now.strftime("%Y-%m-%d"),
        "update_time": now.strftime("%Y-%m-%d %H:%M"),
        "update_failed": False,
        "latest": {
            "numbers": latest_nums,
            "type": draw_type(latest_nums),
            "sum": sum(latest_nums),
            "span": max(latest_nums) - min(latest_nums),
        },
        "history": history,
        "analysis": {
            "hot": hot_nums[:5],
            "cold": cold_nums[:4],
            "miss": {str(k): v for k, v in miss.items()},
            "high_miss": high_miss[:5],
            "avg_sum": avg_sum,
            "sum_range": sum_range,
            "road_ratio": {"0路": road_ratio[0], "1路": road_ratio[1], "2路": road_ratio[2]},
            "text": analysis_text,
        },
        "recommendations": {
            "dan1": today_rec["dan1"],
            "dan2": today_rec["dan2"],
            "dan3": today_rec["dan3"],
            "code5": today_rec["code5"],
            "combos": [{"label": f"重点{i + 1}", "numbers": c} for i, c in enumerate(combos)],
        },
        "backtest": build_backtest(records),
    }


def main():
    now = datetime.now(CST)
    log("=== 福彩3D 自动更新启动 ===")
    log(f"当前北京时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")

    records = fetch_history(50)
    if not records:
        log("All data sources failed. Keeping previous data.")
        mark_update_failed(now)
        raise SystemExit(1)

    output = build_output(records, now)
    DATA_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    latest = output["latest"]["numbers"]
    log(f"更新成功：第 {output['period']} 期，开奖号码 {latest}")


if __name__ == "__main__":
    main()
