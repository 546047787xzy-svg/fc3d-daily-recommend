import requests
import json
from collections import Counter
from datetime import datetime, timezone, timedelta

print("=== 福彩3D 多源自动更新启动 ===")

CST = timezone(timedelta(hours=8))
now = datetime.now(CST)
print(f"当前北京时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")

import os
APP_ID = os.environ.get("MXNZP_APP_ID", "")
APP_SECRET = os.environ.get("MXNZP_APP_SECRET", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
}

raw_list = []

def source_mxnzp_latest():
    """mxnzp - 获取最新一期"""
    try:
        url = f"https://www.mxnzp.com/api/lottery/common/latest?code=fc3d&app_id={APP_ID}&app_secret={APP_SECRET}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 1:
            print(f"❌ mxnzp最新期失败: {data.get('msg')}")
            return []
        item = data["data"]
        nums = [x.strip() for x in item["openCode"].split(",")]
        if len(nums) == 3:
            print(f"✅ mxnzp最新期: {item['expect']} {nums}")
            return [{"expect": item["expect"], "opencode": ",".join(nums), "opentime": item["time"][:10]}]
        return []
    except Exception as e:
        print(f"❌ mxnzp最新期异常: {e}")
        return []

def source_mxnzp_history(size=30):
    """mxnzp - 获取历史记录"""
    try:
        url = f"https://www.mxnzp.com/api/lottery/common/history?code=fc3d&size={size}&app_id={APP_ID}&app_secret={APP_SECRET}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 1:
            print(f"❌ mxnzp历史失败: {data.get('msg')}")
            return []
        items = []
        for item in data["data"]:
            nums = [x.strip() for x in item["openCode"].split(",")]
            if len(nums) == 3:
                items.append({"expect": item["expect"], "opencode": ",".join(nums), "opentime": item["time"][:10]})
        print(f"✅ mxnzp历史: 获取 {len(items)} 期")
        return items
    except Exception as e:
        print(f"❌ mxnzp历史异常: {e}")
        return []

# 先拿历史（包含最新），再补最新
raw_list = source_mxnzp_history(30)
if not raw_list:
    raw_list = source_mxnzp_latest()

if not raw_list:
    print("❌ 所有数据源均失败，退出")
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

def parse_item(item):
    return [int(x) for x in item["opencode"].split(",")]

latest_item = raw_list[0]
latest_nums = parse_item(latest_item)

history = []
for item in raw_list[:10]:
    nums = parse_item(item)
    s = set(nums)
    t = "豹子" if len(s) == 1 else "组三" if len(s) == 2 else "组六"
    history.append({"period": item["expect"], "date": item["opentime"], "numbers": nums, "type": t, "sum": sum(nums), "span": max(nums) - min(nums)})

all_nums_flat = []
all_records = []
for item in raw_list[:30]:
    nums = parse_item(item)
    all_nums_flat.extend(nums)
    all_records.append(nums)

count = Counter(all_nums_flat)
sorted_by_freq = sorted(count.items(), key=lambda x: -x[1])
hot_nums = [n for n, _ in sorted_by_freq[:5]]
cold_nums = [n for n, _ in sorted_by_freq[-4:]]

miss = {}
for digit in range(10):
    miss[digit] = 0
    for rec in all_records:
        if digit in rec:
            break
        miss[digit] += 1

high_miss = sorted([d for d, m in miss.items() if m >= 3], key=lambda x: -miss[x])

sums = [sum(parse_item(item)) for item in raw_list[:10]]
avg_sum = round(sum(sums) / len(sums), 1)
sum_range = "中大和值（10-18）" if avg_sum < 10 else "中小和值（8-16）" if avg_sum > 18 else "中和值（10-18）"

road_counts = [0, 0, 0]
for item in raw_list[:10]:
    for n in parse_item(item):
        road_counts[n % 3] += 1
total_road = sum(road_counts)
road_ratio = [round(c / total_road * 100) for c in road_counts]
min_road = road_counts.index(min(road_counts))
road_digits = {0: [0,3,6,9], 1: [1,4,7], 2: [2,5,8]}

odd_counts = sum(1 for item in raw_list[:10] for n in parse_item(item) if n % 2 == 1)
suggest_more_even = odd_counts > 15

def unique_n(lst, n):
    seen = []
    for x in lst:
        if x not in seen:
            seen.append(x)
        if len(seen) == n:
            break
    return sorted(seen[:n])

dan1 = high_miss[0] if high_miss else hot_nums[0]
dan2 = unique_n(([high_miss[0]] if high_miss else []) + hot_nums, 2)
dan3 = unique_n(hot_nums[:3] + (high_miss[:2] if high_miss else []) + road_digits[min_road], 3)
code5 = unique_n(list(dict.fromkeys(hot_nums[:3] + (high_miss[:3] if high_miss else []))) + hot_nums + cold_nums + list(range(10)), 5)

def pick_combos(pool, n=3):
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

combos = pick_combos(code5, 3)
latest_set = set(latest_nums)
latest_type = "豹子" if len(latest_set) == 1 else "组三" if len(latest_set) == 2 else "组六"

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
    }
}

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"✅ 更新成功！期号: {latest_item['expect']} | 号码: {latest_nums} | 时间: {now.strftime('%Y-%m-%d %H:%M')}")
