import requests
import json
import re
from collections import Counter
from datetime import datetime, timezone, timedelta

print("=== 福彩3D 多源自动更新启动 ===")

CST = timezone(timedelta(hours=8))
now = datetime.now(CST)
print(f"当前北京时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")

# ─────────────────────────────────────────────
# 数据源抓取（多源互备）
# ─────────────────────────────────────────────

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.cwl.gov.cn/",
}

raw_list = []  # 存放所有来源拿到的历史期号，格式: {"expect": "xxx", "opencode": "x,x,x", "opentime": "xxxx-xx-xx"}

def source_cwl_official():
    """福彩官网 - 主力数据源"""
    url = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"
    params = {"name": "3d", "issueCount": 30, "issueStart": "", "issueEnd": "", "dayStart": "", "dayEnd": "", "pageNo": 1, "pageSize": 30, "week": "", "systemType": "PC"}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        result = data.get("result", [])
        items = []
        for item in result:
            code = item.get("code", "")
            nums = re.findall(r"\d", code)
            if len(nums) == 3:
                items.append({
                    "expect": item.get("code", item.get("term", "")),
                    "opencode": ",".join(nums),
                    "opentime": item.get("date", "")[:10]
                })
        print(f"✅ 福彩官网: 获取 {len(items)} 期")
        return items
    except Exception as e:
        print(f"❌ 福彩官网失败: {e}")
        return []

def source_apiplus():
    """apiplus - 备用源1"""
    try:
        r = requests.get("https://f.apiplus.net/fc3d.json", headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        items = []
        for item in data.get("data", [])[:30]:
            code = item.get("opencode", "")
            nums = [x.strip() for x in code.split(",") if x.strip().isdigit()]
            if len(nums) == 3:
                items.append({
                    "expect": item.get("expect", ""),
                    "opencode": ",".join(nums),
                    "opentime": item.get("opentime", "")[:10]
                })
        print(f"✅ apiplus: 获取 {len(items)} 期")
        return items
    except Exception as e:
        print(f"❌ apiplus失败: {e}")
        return []

def source_juhe():
    """聚合数据 - 备用源2（无需key的公开接口）"""
    try:
        r = requests.get("https://api.juhe.cn/lottery/query?lottery_id=CQ3D&key=&page_size=30", headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        items = []
        for item in data.get("result", {}).get("list", [])[:30]:
            code = item.get("lottery_no", "")
            nums = list(code)
            if len(nums) == 3 and all(n.isdigit() for n in nums):
                items.append({
                    "expect": item.get("lottery_id", ""),
                    "opencode": ",".join(nums),
                    "opentime": item.get("lottery_date", "")[:10]
                })
        print(f"✅ 聚合数据: 获取 {len(items)} 期")
        return items
    except Exception as e:
        print(f"❌ 聚合数据失败: {e}")
        return []

def source_17500():
    """500彩票网 - 备用源3"""
    try:
        url = "https://datachart.500.com/fc3d/history/newinc/history.php?start=100&end=999"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        # 解析HTML中的数据
        pattern = r'<tr[^>]*>.*?<td[^>]*>(\d{7,8})</td>.*?<td[^>]*>(\d)</td>.*?<td[^>]*>(\d)</td>.*?<td[^>]*>(\d)</td>'
        matches = re.findall(pattern, r.text, re.DOTALL)
        items = []
        for m in matches[:30]:
            items.append({
                "expect": m[0],
                "opencode": f"{m[1]},{m[2]},{m[3]}",
                "opentime": ""
            })
        print(f"✅ 500彩票网: 获取 {len(items)} 期")
        return items
    except Exception as e:
        print(f"❌ 500彩票网失败: {e}")
        return []

def source_sina():
    """新浪彩票 - 备用源4"""
    try:
        r = requests.get("https://lottery.sina.com.cn/api/lotteryHistoryList?lottery_id=fc3d&size=30", headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        items = []
        for item in data.get("data", {}).get("list", [])[:30]:
            code = item.get("winning_num", "")
            nums = [x.strip() for x in code.split() if x.strip().isdigit()]
            if len(nums) == 3:
                items.append({
                    "expect": item.get("period_id", ""),
                    "opencode": ",".join(nums),
                    "opentime": item.get("draw_time", "")[:10]
                })
        print(f"✅ 新浪彩票: 获取 {len(items)} 期")
        return items
    except Exception as e:
        print(f"❌ 新浪彩票失败: {e}")
        return []

# ─────────────────────────────────────────────
# 依次尝试各数据源，取第一个成功的作为主数据
# ─────────────────────────────────────────────
sources = [source_cwl_official, source_apiplus, source_17500, source_sina, source_juhe]
for src in sources:
    result = src()
    if result and len(result) >= 5:
        raw_list = result
        break

if not raw_list:
    print("❌ 所有数据源均失败，退出")
    # 保留旧数据不覆盖
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

# ─────────────────────────────────────────────
# 解析数据
# ─────────────────────────────────────────────
def parse_item(item):
    nums = [int(x) for x in item["opencode"].split(",")]
    return nums

latest_item = raw_list[0]
latest_nums = parse_item(latest_item)

# 历史记录（最近10期展示用）
history = []
for item in raw_list[:10]:
    nums = parse_item(item)
    s = set(nums)
    if len(s) == 1:
        t = "豹子"
    elif len(s) == 2:
        t = "组三"
    else:
        t = "组六"
    history.append({
        "period": item["expect"],
        "date": item["opentime"],
        "numbers": nums,
        "type": t,
        "sum": sum(nums),
        "span": max(nums) - min(nums)
    })

# ─────────────────────────────────────────────
# 综合分析（基于近30期）
# ─────────────────────────────────────────────
all_nums_flat = []
all_records = []
for item in raw_list[:30]:
    nums = parse_item(item)
    all_nums_flat.extend(nums)
    all_records.append(nums)

# 1. 频率分析（热冷码）
count = Counter(all_nums_flat)
freq = {i: count.get(i, 0) for i in range(10)}
sorted_by_freq = sorted(freq.items(), key=lambda x: -x[1])
hot_nums = [n for n, _ in sorted_by_freq[:5]]   # 热码前5
cold_nums = [n for n, _ in sorted_by_freq[-4:]] # 冷码后4

# 2. 遗漏分析（每个数字距上次出现的期数）
miss = {}
for digit in range(10):
    miss[digit] = 0
    for rec in all_records:
        if digit in rec:
            break
        miss[digit] += 1

# 高遗漏（遗漏>=3期）
high_miss = sorted([d for d, m in miss.items() if m >= 3], key=lambda x: -miss[x])

# 3. 和值分析（近10期）
sums = [sum(parse_item(item)) for item in raw_list[:10]]
avg_sum = round(sum(sums) / len(sums), 1)
# 和值区间建议
if avg_sum < 10:
    sum_range = "中大和值（10-18）"
elif avg_sum > 18:
    sum_range = "中小和值（8-16）"
else:
    sum_range = "中和值（10-18）"

# 4. 012路分析（近10期）
road_counts = [0, 0, 0]
for item in raw_list[:10]:
    for n in parse_item(item):
        road_counts[n % 3] += 1
total_road = sum(road_counts)
road_ratio = [round(c / total_road * 100) for c in road_counts]
# 哪路偏少
min_road = road_counts.index(min(road_counts))
# 该路的数字
road_digits = {0: [0,3,6,9], 1: [1,4,7], 2: [2,5,8]}

# 5. 奇偶分析（近10期）
odd_counts = sum(1 for item in raw_list[:10] for n in parse_item(item) if n % 2 == 1)
even_counts = 30 - odd_counts
# 如果近期奇多，建议偶多组合
suggest_more_even = odd_counts > even_counts

# ─────────────────────────────────────────────
# 生成推荐（综合多维分析）
# ─────────────────────────────────────────────

def unique3(lst):
    seen = []
    for x in lst:
        if x not in seen:
            seen.append(x)
        if len(seen) == 3:
            break
    return sorted(seen[:3])

def unique_n(lst, n):
    seen = []
    for x in lst:
        if x not in seen:
            seen.append(x)
        if len(seen) == n:
            break
    return sorted(seen[:n])

# 独胆：热码第1 且 遗漏不过大
dan1_candidates = hot_nums[:3]
if high_miss:
    dan1_candidates = [high_miss[0]] + hot_nums[:2]
dan1 = dan1_candidates[0]

# 双胆：热码+遗漏结合
if high_miss:
    dan2 = unique_n([high_miss[0]] + hot_nums, 2)
else:
    dan2 = unique_n(hot_nums, 2)

# 三胆：热码+遗漏+012路补充
dan3_pool = list(dict.fromkeys(hot_nums[:3] + high_miss[:2] + road_digits[min_road]))
dan3 = unique_n(dan3_pool, 3)

# 5码参考：热码3 + 遗漏2
code5_pool = list(dict.fromkeys(hot_nums[:3] + high_miss[:3]))
code5 = unique_n(code5_pool, 5)
if len(code5) < 5:
    code5 = unique_n(hot_nums + cold_nums + list(range(10)), 5)

# 重点推荐3注（从5码中挑）
def pick_combos(pool, n=3):
    combos = []
    pool = sorted(set(pool))
    # 优先包含独胆的组合
    for i in range(len(pool)):
        for j in range(i, len(pool)):
            for k in range(j, len(pool)):
                c = [pool[i], pool[j], pool[k]]
                if dan1 in c:
                    combos.append(c)
                if len(combos) >= n:
                    return combos
    # 补充
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

# ─────────────────────────────────────────────
# 组装输出
# ─────────────────────────────────────────────
latest_set = set(latest_nums)
if len(latest_set) == 1:
    latest_type = "豹子"
elif len(latest_set) == 2:
    latest_type = "组三"
else:
    latest_type = "组六"

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
    "latest": {
        "numbers": latest_nums,
        "type": latest_type,
        "sum": sum(latest_nums),
        "span": max(latest_nums) - min(latest_nums)
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
        "text": analysis_text
    },
    "recommendations": {
        "dan1": dan1,
        "dan2": dan2,
        "dan3": dan3,
        "code5": code5,
        "combos": [
            {"label": f"重点{i+1}", "numbers": c}
            for i, c in enumerate(combos)
        ]
    }
}

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"✅ 更新成功！期号: {latest_item['expect']} | 号码: {latest_nums} | 时间: {now.strftime('%Y-%m-%d %H:%M')}")
