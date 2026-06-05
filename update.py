import requests
import json
import os
from collections import Counter
from datetime import datetime, timezone, timedelta

print("=== 福彩3D 自动更新启动 ===")

CST = timezone(timedelta(hours=8))
now = datetime.now(CST)
print(f"当前北京时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")

APP_ID = os.environ.get("MXNZP_APP_ID", "")
APP_SECRET = os.environ.get("MXNZP_APP_SECRET", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
}

def fetch_history(size=50):
    try:
        url = f"https://www.mxnzp.com/api/lottery/common/history?code=fc3d&size={size}&app_id={APP_ID}&app_secret={APP_SECRET}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 1:
            print(f"❌ 失败: {data.get('msg')}")
            return []
        items = []
        for item in data["data"]:
            nums = [x.strip() for x in item["openCode"].split(",")]
            if len(nums) == 3:
                items.append({"expect": item["expect"], "opencode": ",".join(nums), "opentime": item["time"][:10]})
        print(f"✅ 获取 {len(items)} 期")
        return items
    except Exception as e:
        print(f"❌ 异常: {e}")
        return []

raw_list = fetch_history(50)

if not raw_list:
    print("❌ 数据源失败，保留旧数据")
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            old = json.load(f)
        old["update_failed"] = True
        old["failed_time"] = now.strftime("%Y-%m-%d %H:%M")
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(old, f, ensure_ascii=False, indent=2)
    except:
        pass
    exit(1)

def parse_nums(item):
    return [int(x) for x in item["opencode"].split(",")]

def unique_n(lst, n):
    seen = []
    for x in lst:
        if x not in seen:
            seen.append(x)
        if len(seen) == n:
            break
    return sorted(seen[:n])

def analyze(records):
    all_flat, all_recs = [], []
    for item in records[:30]:
        nums = parse_nums(item)
        all_flat.extend(nums)
        all_recs.append(nums)
    count = Counter(all_flat)
    sf = sorted(count.items(), key=lambda x: -x[1])
    hot = [n for n, _ in sf[:5]]
    cold = [n for n, _ in sf[-4:]]
    miss = {}
    for d in range(10):
        miss[d] = 0
        for rec in all_recs:
            if d in rec:
                break
            miss[d] += 1
    hm = sorted([d for d, m in miss.items() if m >= 3], key=lambda x: -miss[x])
    road_counts = [0, 0, 0]
    for item in records[:10]:
        for n in parse_nums(item):
            road_counts[n % 3] += 1
    min_road = road_counts.index(min(road_counts))
    road_digits = {0: [0,3,6,9], 1: [1,4,7], 2: [2,5,8]}
    dan1 = hm[0] if hm else hot[0]
    dan2 = unique_n(([hm[0]] if hm else []) + hot, 2)
    dan3 = unique_n(hot[:3] + (hm[:2] if hm else []) + road_digits[min_road], 3)
    code5 = unique_n(list(dict.fromkeys(hot[:3] + (hm[:3] if hm else []))) + hot + cold + list(range(10)), 5)
    return {"dan1": dan1, "dan2": dan2, "dan3": dan3, "code5": code5, "miss": miss, "hot": hot, "cold": cold}

# ── 回测 ──
print("=== 回测 ===")
backtest_results = []
total = h1 = h2 = h3 = h5 = 0
max_bt = min(len(raw_list) - 30, 70)
for i in range(max_bt):
    target = raw_list[i]
    hist = raw_list[i+1:i+31]
    if len(hist) < 10:
        continue
    rec = analyze(hist)
    actual = parse_nums(target)
    d1 = rec["dan1"] in actual
    d2 = any(d in actual for d in rec["dan2"])
    d3 = any(d in actual for d in rec["dan3"])
    c5 = all(n in rec["code5"] for n in actual)  # 严格：3个全中才算
    total += 1
    if d1: h1 += 1
    if d2: h2 += 1
    if d3: h3 += 1
    if c5: h5 += 1
    backtest_results.append({
        "period": target["expect"], "date": target["opentime"], "actual": actual,
        "dan1": rec["dan1"], "dan2": rec["dan2"], "dan3": rec["dan3"], "code5": rec["code5"],
        "dan1_hit": d1, "dan2_hit": d2, "dan3_hit": d3, "code5_hit": c5,
    })

def pct(a, b):
    return round(a / b * 100, 1) if b > 0 else 0

backtest_summary = {
    "total": total,
    "dan1": {"hit": h1, "rate": pct(h1, total), "random_rate": 30.0},
    "dan2": {"hit": h2, "rate": pct(h2, total), "random_rate": 51.2},
    "dan3": {"hit": h3, "rate": pct(h3, total), "random_rate": 65.7},
    "code5": {"hit": h5, "rate": pct(h5, total), "random_rate": 8.3},
}
print(f"回测{total}期 | 独胆{backtest_summary['dan1']['rate']}% 双胆{backtest_summary['dan2']['rate']}% 三胆{backtest_summary['dan3']['rate']}% 5码(严格){backtest_summary['code5']['rate']}%")

# ── 当期分析 ──
latest_item = raw_list[0]
latest_nums = parse_nums(latest_item)
latest_set = set(latest_nums)
latest_type = "豹子" if len(latest_set) == 1 else "组三" if len(latest_set) == 2 else "组六"

history = []
for item in raw_list[:10]:
    nums = parse_nums(item)
    s = set(nums)
    t = "豹子" if len(s) == 1 else "组三" if len(s) == 2 else "组六"
    history.append({"period": item["expect"], "date": item["opentime"], "numbers": nums, "type": t, "sum": sum(nums), "span": max(nums) - min(nums)})

today_rec = analyze(raw_list[1:31] if len(raw_list) > 31 else raw_list[1:])

all_flat = []
for item in raw_list[:30]:
    all_flat.extend(parse_nums(item))
count = Counter(all_flat)
sf = sorted(count.items(), key=lambda x: -x[1])
hot_nums = [n for n, _ in sf[:5]]
cold_nums = [n for n, _ in sf[-4:]]

miss = today_rec["miss"]
high_miss = sorted([d for d, m in miss.items() if m >= 3], key=lambda x: -miss[x])

road_counts = [0, 0, 0]
for item in raw_list[:10]:
    for n in parse_nums(item):
        road_counts[n % 3] += 1
total_road = sum(road_counts)
road_ratio = [round(c / total_road * 100) for c in road_counts]
min_road = road_counts.index(min(road_counts))
road_digits = {0: [0,3,6,9], 1: [1,4,7], 2: [2,5,8]}

odd_counts = sum(1 for item in raw_list[:10] for n in parse_nums(item) if n % 2 == 1)
suggest_more_even = odd_counts > 15

sums = [sum(parse_nums(item)) for item in raw_list[:10]]
avg_sum = round(sum(sums) / len(sums), 1)
sum_range = "中大和值（10-18）" if avg_sum < 10 else "中小和值（8-16）" if avg_sum > 18 else "中和值（10-18）"

dan1, dan2, dan3, code5 = today_rec["dan1"], today_rec["dan2"], today_rec["dan3"], today_rec["code5"]

def pick_combos(pool, dan1, n=3):
    combos = []
    pool = sorted(set(pool))
    for i in range(len(pool)):
        for j in range(i, len(pool)):
            for k in range(j, len(pool)):
                c = [pool[i], pool[j], pool[k]]
                if dan1 in c and c not in combos:
                    combos.append(c)
                if len(combos) >= n:
                    return combos
    for i in range(len(pool)):
        for j in range(i, len(pool)):
            for k in range(j, len(pool)):
                c = [pool[i], pool[j], pool[k]]
                if c not in combos:
                    combos.append(c)
                if len(combos) >= n:
                    return combos
    return combos[:n]

combos = pick_combos(code5, dan1, 3)

analysis_text = (
    f"近30期热码为 {hot_nums[:4]}，冷码为 {cold_nums[:3]}。"
    f"高遗漏号码：{high_miss[:3] if high_miss else '无'}。"
    f"近10期和值均值 {avg_sum}，建议关注{sum_range}。"
    f"012路近期分布：0路{road_ratio[0]}%、1路{road_ratio[1]}%、2路{road_ratio[2]}%，"
    f"{min_road}路偏少，可适当补充{road_digits[min_road][:3]}。"
    f"{'近期奇码偏多，建议搭配偶码。' if suggest_more_even else '近期偶码偏多，建议搭配奇码。'}"
)

output = {
    "period": latest_item["expect"],
    "date": latest_item["opentime"] or now.strftime("%Y-%m-%d"),
    "update_time": now.strftime("%Y-%m-%d %H:%M"),
    "update_failed": False,
    "latest": {"numbers": latest_nums, "type": latest_type, "sum": sum(latest_nums), "span": max(latest_nums) - min(latest_nums)},
    "history": history,
    "analysis": {
        "hot": hot_nums[:5], "cold": cold_nums[:4],
        "miss": {str(k): v for k, v in miss.items()},
        "high_miss": high_miss[:5], "avg_sum": avg_sum, "sum_range": sum_range,
        "road_ratio": {"0路": road_ratio[0], "1路": road_ratio[1], "2路": road_ratio[2]},
        "text": analysis_text
    },
    "recommendations": {
        "dan1": dan1, "dan2": dan2, "dan3": dan3, "code5": code5,
        "combos": [{"label": f"重点{i+1}", "numbers": c} for i, c in enumerate(combos)]
    },
    "backtest": {"summary": backtest_summary, "details": backtest_results[:50]}
}

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"✅ 更新成功！期号: {latest_item['expect']} | 号码: {latest_nums} | 时间: {now.strftime('%Y-%m-%d %H:%M')}")
