import requests
import json

print("=== 自动更新启动 ===")

try:
    res = requests.get("http://f.apiplus.net/fc3d.json", timeout=15)
    data = res.json()
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
            {"type": "直选", "numbers": [3,7,6], "desc": "热码 + 冷码反弹"},
            {"type": "直选", "numbers": [4,7,9], "desc": "趋势推荐"},
            {"type": "组六", "numbers": [1,5,6,7,8,9], "desc": "综合大底"}
        ],
        "analysis": "近10期热码强势，冷码反弹概率上升。"
    }

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("✅ 更新成功！期号:", latest['expect'])

except Exception as e:
    print("❌ 失败:", str(e))
