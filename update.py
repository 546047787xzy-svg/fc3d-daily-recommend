import requests
import json
from collections import Counter

print("=== 启动聪明模式（动态分析） ===")

API_URL = "http://f.apiplus.net/fc3d.json"

try:
    res = requests.get(API_URL, timeout=15)
    data = res.json()
    draws = data['data'][:15]

    all_numbers = []
    for d in draws:
        all_numbers.extend([int(x) for x in d['opencode'].split(',')])

    count = Counter(all_numbers)
    hot = [num for num, _ in count.most_common(6)]
    cold = [num for num, _ in sorted(count.items(), key=lambda x: x[1])[:5]]

    rec1 = sorted(set(hot[:3] + [cold[0]]))[:3]
    rec2 = sorted(set(hot[1:4] + [cold[1]]))[:3]
    rec3 = sorted(set(hot[:4] + cold[:2]))[:6]

    latest = data['data'][0]
    numbers = [int(x) for x in latest['opencode'].split(',')]

    output = {
        "period": latest['expect'],
        "date": latest['opentime'][:10],
        "trial": "573",
        "latest": {
            "numbers": numbers,
            "type": "组六" if len(set(numbers)) == 3 else "组三",
            "sum": sum(numbers),
            "span": max(numbers) - min(numbers)
        },
        "recommendations": [
            {"type": "直选", "numbers": rec1, "desc": "热码为主 + 冷码反弹"},
            {"type": "直选", "numbers": rec2, "desc": "趋势分析推荐"},
            {"type": "组六", "numbers": rec3, "desc": "综合热冷码大底"}
        ],
        "analysis": f"近15期热码{hot[:4]}强势，冷码{cold[:3]}出现概率上升。建议以热码为主，搭配冷码反弹。"
    }

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ 聪明模式更新成功！期号: {latest['expect']}")

except Exception as e:
    print("❌ 更新失败:", str(e))
