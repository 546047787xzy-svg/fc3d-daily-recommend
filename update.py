import requests
import json
from collections import Counter
from datetime import datetime

print("=== 福彩3D 完全自动更新启动 ===")

try:
    # 获取最新数据（包含历史）
    response = requests.get("http://f.apiplus.net/fc3d.json", timeout=20)
    response.raise_for_status()
    data = response.json()
    
    # 最新一期
    latest = data['data'][0]
    numbers = [int(x) for x in latest['opencode'].split(',')]
    
    # 取最近10期作为历史记录
    history = []
    for item in data['data'][:10]:
        nums = [int(x) for x in item['opencode'].split(',')]
        history.append({
            "period": item['expect'],
            "numbers": nums,
            "type": "组六" if len(set(nums)) == 3 else "组三"
        })
    
    # 热冷码分析
    all_numbers = []
    for item in data['data'][:15]:
        all_numbers.extend([int(x) for x in item['opencode'].split(',')])
    
    count = Counter(all_numbers)
    hot = [num for num, _ in count.most_common(6)]
    cold = [num for num, _ in sorted(count.items(), key=lambda x: x[1])[:5]]
    
    # 生成推荐
    rec1 = sorted(set(hot[:3] + [cold[0]]))[:3]
    rec2 = sorted(set(hot[1:4] + [cold[1]]))[:3]
    rec3 = sorted(set(hot[:4] + cold[:3]))[:6]

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
        "history": history,
        "recommendations": [
            {"type": "直选", "numbers": rec1, "desc": "热码为主 + 冷码反弹"},
            {"type": "直选", "numbers": rec2, "desc": "趋势分析推荐"},
            {"type": "组六", "numbers": rec3, "desc": "综合热冷码大底"}
        ],
        "analysis": f"近15期热码{hot[:4]}强势，冷码{cold[:3]}反弹概率上升。建议以热码为主，搭配冷码。"
    }

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ 完全自动更新成功！期号: {latest['expect']} 时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

except Exception as e:
    print(f"❌ 更新失败: {str(e)}")
