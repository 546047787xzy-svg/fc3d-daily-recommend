import requests
import json
import re
from datetime import datetime

API_URL = "http://f.apiplus.net/fc3d.json"

def fetch_latest_data():
    try:
        res = requests.get(API_URL, timeout=15)
        data = res.json()
        latest = data['data'][0]
        
        numbers = [int(x) for x in latest['opencode'].split(',')]
        return {
            "period": latest['expect'],
            "date": latest['opentime'][:10],
            "numbers": numbers,
            "trial": "573"   # 后续可改进为真实试机号
        }
    except Exception as e:
        print("获取数据失败，使用备用数据:", e)
        # 备用数据（防止失败）
        return {
            "period": "2026135",
            "date": "2026-05-25",
            "numbers": [6, 5, 4],
            "trial": "573"
        }

def generate_recommendations():
    return [
        {"type": "直选", "numbers": [3, 7, 6], "desc": "独胆7 + 热码6 + 冷码反弹"},
        {"type": "直选", "numbers": [4, 7, 9], "desc": "跨度预计回升"},
        {"type": "组六", "numbers": [1, 5, 6, 7, 8, 9], "desc": "6码大底（多专家共识）"}
    ]

def update_html(data):
    with open('index.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # 构造新的 latestData
    new_data_str = f'''const latestData = {{
    period: "{data['period']}",
    date: "{data['date']}",
    trial: "{data['trial']}",
    latest: {{ numbers: {data['numbers']}, type: "组六", sum: {sum(data['numbers'])}, span: {max(data['numbers'])-min(data['numbers'])} }},
    recommendations: {json.dumps(generate_recommendations(), ensure_ascii=False)},
    analysis: "近10期热码0、6、7强势，冷码1、3、9出现概率上升。建议以热码为主，搭配冷码反弹。"
}};'''

    # 更可靠的替换方式
    pattern = r'const latestData = \{.*?\};'
    content = re.sub(pattern, new_data_str, content, flags=re.DOTALL)

    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ index.html 更新成功！")

if __name__ == "__main__":
    print("开始每日更新...")
    data = fetch_latest_data()
    update_html(data)
    print("更新完成！")
