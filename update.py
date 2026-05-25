import requests
import json

print("=== 开始执行 update.py ===")

API_URL = "http://f.apiplus.net/fc3d.json"

try:
    print("正在请求 API...")
    res = requests.get(API_URL, timeout=15)
    print("API 请求成功，状态码:", res.status_code)
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
            {"type": "组六", "numbers": [1, 5, 6, 7, 8, 9], "desc": "6码大底"}
        ],
        "analysis": "近10期热码0、6、7强势，冷码1、3、9出现概率上升。"
    }
    
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print("✅ data.json 更新成功！")
    
except Exception as e:
    print("❌ 发生错误:", str(e))
    # 即使出错也生成一个默认文件
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump({"error": str(e)}, f, ensure_ascii=False)
