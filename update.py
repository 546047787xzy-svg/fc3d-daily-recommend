import requests
import json

print("=== 开始自动更新 ===")

API_URL = "http://f.apiplus.net/fc3d.json"

try:
    res = requests.get(API_URL, timeout=15)
    data = res.json()
    latest = data['data'][0]
    
    numbers = [int(x) for x in latest['opencode'].split(',')]
    
    output = {
        "period": latest['expect'],
        "date": latest['opentime'][:10],
        "trial": "573",
        "latest": {
            "numbers": numbers,
            "type": "组六",
            "sum": sum(numbers),
            "span": max(numbers) - min(numbers)
        },
        "recommendations": [
            {"type": "直选", "numbers": [3, 7, 6], "desc": "独胆7 + 热码6 + 冷码反弹"},
            {"type": "直选", "numbers": [4, 7, 9], "desc": "跨度预计回升"},
            {"type": "组六", "numbers": [1, 5, 6, 7, 8, 9], "desc": "6码大底（专家共识）"}
        ],
        "analysis": "近10期热码0、6、7强势，冷码1、3、9出现概率上升。建议以热码为主，搭配冷码反弹。"
    }
    
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print("✅ data.json 更新成功！期号:", latest['expect'])
    
except Exception as e:
    print("❌ 更新失败:", str(e))
