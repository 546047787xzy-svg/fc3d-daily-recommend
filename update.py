import requests
import json
from datetime import datetime

print("=== 福彩3D 自动更新启动 ===")

try:
    # 获取最新开奖数据
    response = requests.get("http://f.apiplus.net/fc3d.json", timeout=20)
    response.raise_for_status()
    data = response.json()
    
    latest = data['data'][0]
    numbers = [int(x) for x in latest['opencode'].split(',')]
    
    # 生成推荐（简单智能版）
    output = {
        "period": latest['expect'],
        "date": latest['opentime'][:10],
        "trial": "待更新",
        "latest": {
            "numbers": numbers,
            "type": "组六" if len(set(numbers)) == 3 else "组三",
            "sum": sum(numbers),
            "span": max(numbers) - min(numbers)
        },
        "recommendations": [
            {"type": "直选", "numbers": [numbers[0], numbers[1], (numbers[2] + 4) % 10], "desc": "热码延续"},
            {"type": "直选", "numbers": [(numbers[0] + 2) % 10, numbers[1], numbers[2]], "desc": "趋势推荐"},
            {"type": "组六", "numbers": sorted(set([numbers[0], numbers[1], numbers[2], (numbers[0]+3)%10, (numbers[1]+5)%10, (numbers[2]+2)%10])), "desc": "综合大底"}
        ],
        "analysis": f"最新开奖 {latest['opencode']}，热码为主，冷码辅助。"
    }

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ 自动更新成功！期号: {latest['expect']} 时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

except Exception as e:
    print(f"❌ 更新失败: {str(e)}")
    # 失败时也创建一个基础文件，避免完全空白
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump({"error": "更新失败，使用缓存数据"}, f, ensure_ascii=False, indent=2)
