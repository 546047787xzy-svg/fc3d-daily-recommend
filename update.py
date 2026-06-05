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
    try:
        records = fetch_from_mxnzp(size)
        records = sorted(records, key=lambda x: x["expect"], reverse=True)
        if records:
            log(f"Fetched {len(records)} records from mxnzp.com.")
            return records
    except Exception as exc:
        log(f"Fetch failed from mxnzp.com: {exc}")
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


def draw_type(nums):
    unique_count = len(set(nums))
    if unique_count == 1:
        return "豹子"
    if unique_count == 2:
        return "组三"
    return "组六"


def stable_unique(values, limit):
    result = []
    for value in values:
        if value not in result:
            result.append(value)
        if len(result) >= limit:
            break
    return result


def digit_metrics(records):
    count_30 = Counter()
    count_15 = Counter()
    count_10 = Counter()
    miss = {digit: 0 for digit in range(10)}

    recs_30 = [parse_nums(item) for item in records[:30]]
    recs_15 = [parse_nums(item) for item in records[:15]]
    recs_10 = [parse_nums(item) for item in records[:10]]

    for rec in recs_30:
        count_30.update(rec)
    for rec in recs_15:
        count_15.update(rec)
    for rec in recs_10:
        count_10.update(rec)

    for digit in range(10):
        for rec in recs_30:
            if digit in rec:
                break
            miss[digit] += 1

    scores = {}
    for digit in range(10):
        scores[digit] = (
            count_30[digit] * 1.0
            + count_15[digit] * 0.8
            + count_10[digit] * 0.6
            + min(miss[digit], 4) * 0.35
        )

    hot = [digit for digit, _ in sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:5]]
    cold = [digit for digit, _ in sorted(scores.items(), key=lambda x: (x[1], x[0]))[:4]]
    high_miss = [digit for digit, _ in sorted(miss.items(), key=lambda x: (-x[1], x[0])) if miss[digit] >= 4][:5]

    return {
        "count_30": count_30,
        "count_15": count_15,
        "count_10": count_10,
        "miss": miss,
        "scores": scores,
        "hot": hot,
        "cold": cold,
        "high_miss": high_miss,
    }


def calc_window_features(records):
    recent10 = [parse_nums(item) for item in records[:10]]
    sums = [sum(nums) for nums in recent10]
    avg_sum = round(sum(sums) / len(sums), 1) if sums else 0

    if avg_sum < 10:
        sum_range = "中大和值（10-18）"
        target_sum_min, target_sum_max = 10, 18
    elif avg_sum > 18:
        sum_range = "中小和值（8-16）"
        target_sum_min, target_sum_max = 8, 16
    else:
        sum_range = "中和值（10-18）"
        target_sum_min, target_sum_max = 10, 18

    road_counts = [0, 0, 0]
    for nums in recent10:
        for n in nums:
            road_counts[n % 3] += 1
    total_road = sum(road_counts) or 1
    road_ratio = [round(c / total_road * 100) for c in road_counts]
    weak_road = road_counts.index(min(road_counts))
    road_digits = {0: [0, 3, 6, 9], 1: [1, 4, 7], 2: [2, 5, 8]}

    odd_count = sum(1 for nums in recent10 for n in nums if n % 2 == 1)
    prefer_even = odd_count > 15

    return {
        "avg_sum": avg_sum,
        "sum_range": sum_range,
        "target_sum_min": target_sum_min,
        "target_sum_max": target_sum_max,
        "road_ratio": {"0路": road_ratio[0], "1路": road_ratio[1], "2路": road_ratio[2]},
        "weak_road": weak_road,
        "road_digits": road_digits,
        "prefer_even": prefer_even,
    }


def score_combo(combo, metrics, features):
    s = sum(combo)
    span = max(combo) - min(combo)
    unique_count = len(set(combo))
    odd_count = sum(1 for n in combo if n % 2 == 1)
    weak_road_hits = sum(1 for n in combo if n % 3 == features["weak_road"])

    score = sum(metrics["scores"][n] for n in combo)
    score += min(weak_road_hits, 2) * 0.45
    score += 0.35 if features["target_sum_min"] <= s <= features["target_sum_max"] else -0.8
    score += 0.2 if 2 <= span <= 7 else -0.35
    score += 0.15 if unique_count >= 2 else -0.6

    if features["prefer_even"]:
        score += 0.2 if odd_count <= 1 else -0.2
    else:
        score += 0.2 if odd_count >= 2 else -0.2

    if combo[0] == combo[1] == combo[2]:
        score -= 1.5

    return round(score, 4)


def select_display_combos(top_combos, limit=3):
    picked = []
    used_signatures = set()

    for item in top_combos:
        combo = item["numbers"]
        unique_count = len(set(combo))
        if unique_count == 1:
            continue

        signature = tuple(sorted(set(combo)))
        if signature in used_signatures:
            continue

        picked.append(item)
        used_signatures.add(signature)
        if len(picked) >= limit:
            break

    if len(picked) < limit:
        for item in top_combos:
            combo = item["numbers"]
            if len(set(combo)) == 1:
                continue
            if item in picked:
                continue
            picked.append(item)
            if len(picked) >= limit:
                break

    return picked[:limit]


def analyze(records):
    metrics = digit_metrics(records)
    features = calc_window_features(records)

    ranked_digits = [digit for digit, _ in sorted(metrics["scores"].items(), key=lambda x: (-x[1], x[0]))]
    hot = metrics["hot"]
    cold = metrics["cold"]
    miss = metrics["miss"]
    high_miss = metrics["high_miss"]

    dan1 = hot[0]
    dan2 = sorted(stable_unique(hot[:3] + high_miss[:1], 2))
    dan3 = sorted(stable_unique(hot[:4] + features["road_digits"][features["weak_road"]][:1], 3))
    code5 = sorted(stable_unique(hot[:5] + high_miss[:2], 5))

    candidate_pool = stable_unique(
        hot[:5] + ranked_digits[:6] + features["road_digits"][features["weak_road"]][:2] + high_miss[:2],
        7,
    )
    candidate_pool = sorted(candidate_pool)

    combos = []
    for i in range(len(candidate_pool)):
        for j in range(i, len(candidate_pool)):
            for k in range(j, len(candidate_pool)):
                combo = [candidate_pool[i], candidate_pool[j], candidate_pool[k]]
                if dan1 not in combo and not any(d in combo for d in dan2):
                    continue
                combo_score = score_combo(combo, metrics, features)
                combos.append(
                    {
                        "numbers": combo,
                        "score": combo_score,
                        "sum": sum(combo),
                        "span": max(combo) - min(combo),
                    }
                )

    combos.sort(key=lambda item: (-item["score"], item["sum"], item["span"], item["numbers"]))

    return {
        "dan1": dan1,
        "dan2": dan2,
        "dan3": dan3,
        "code5": code5,
        "miss": miss,
        "hot": hot,
        "cold": cold,
        "high_miss": high_miss,
        "avg_sum": features["avg_sum"],
        "sum_range": features["sum_range"],
        "road_ratio": features["road_ratio"],
        "weak_road": features["weak_road"],
        "prefer_even": features["prefer_even"],
        "candidate_pool": candidate_pool,
        "top_combos": combos[:8],
    }


def build_backtest(records):
    details = []
    total = h1 = h2 = h3 = h5 = combo_hit = 0
    max_bt = min(len(records) - 30, 20)

    for i in range(max_bt):
        target = records[i]
        history = records[i + 1 : i + 31]
        if len(history) < 10:
            continue

        rec = analyze(history)
        actual = parse_nums(target)
        actual_sorted = sorted(actual)

        d1 = rec["dan1"] in actual
        d2 = any(d in actual for d in rec["dan2"])
        d3 = any(d in actual for d in rec["dan3"])
        c5 = all(n in rec["code5"] for n in actual)
        combo_ok = any(sorted(item["numbers"]) == actual_sorted for item in rec["top_combos"][:3])

        total += 1
        h1 += int(d1)
        h2 += int(d2)
        h3 += int(d3)
        h5 += int(c5)
        combo_hit += int(combo_ok)
        details.append(
            {
                "period": target["expect"],
                "date": target["opentime"],
                "actual": actual,
                "dan1": rec["dan1"],
                "dan2": rec["dan2"],
                "dan3": rec["dan3"],
                "code5": rec["code5"],
                "top_combo": rec["top_combos"][0]["numbers"] if rec["top_combos"] else [],
                "dan1_hit": d1,
                "dan2_hit": d2,
                "dan3_hit": d3,
                "code5_hit": c5,
                "combo_hit": combo_ok,
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
            "combo3": {"hit": combo_hit, "rate": pct(combo_hit), "random_rate": 0.3},
        },
        "details": details[:20],
    }


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
    parity_tip = "近期奇码偏多，建议搭配偶码。" if today_rec["prefer_even"] else "近期偶码偏多，建议搭配奇码。"
    weak_road_digits = today_rec["candidate_pool"]
    display_combos = select_display_combos(today_rec["top_combos"], 3)

    analysis_text = (
        f"近30期热码为 {today_rec['hot'][:4]}，冷码为 {today_rec['cold'][:3]}。"
        f"高遗漏号码为 {today_rec['high_miss'][:3] if today_rec['high_miss'] else '暂无'}。"
        f"近10期和值均值 {today_rec['avg_sum']}，建议关注{today_rec['sum_range']}。"
        f"012路分布：0路{today_rec['road_ratio']['0路']}%，1路{today_rec['road_ratio']['1路']}%，"
        f"2路{today_rec['road_ratio']['2路']}%，{today_rec['weak_road']}路偏少。"
        f"候选号码以热号为主，结合弱势路与遗漏做轻微修正，收敛到 {weak_road_digits[:5]}。"
        f"{parity_tip}"
    )

    output = {
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
            "hot": today_rec["hot"][:5],
            "cold": today_rec["cold"][:4],
            "miss": {str(k): v for k, v in today_rec["miss"].items()},
            "high_miss": today_rec["high_miss"][:5],
            "avg_sum": today_rec["avg_sum"],
            "sum_range": today_rec["sum_range"],
            "road_ratio": today_rec["road_ratio"],
            "text": analysis_text,
        },
        "recommendations": {
            "dan1": today_rec["dan1"],
            "dan2": today_rec["dan2"],
            "dan3": today_rec["dan3"],
            "code5": today_rec["code5"],
            "combos": [
                {"label": f"重点{i + 1}", "numbers": item["numbers"]}
                for i, item in enumerate(display_combos)
            ],
        },
        "backtest": build_backtest(records),
    }
    return output


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
