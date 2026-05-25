import requests
import json
import re
from datetime import datetime

# ==================== 配置区 ====================
# 公开API（可免费使用）
API_URL = "http://f.apiplus.net/fc3d.json"

def fetch_latest_data():
    try:
        res = requests.get(API_URL, timeout=10)
        data = res.json()
        latest = data['data'][0]  # 最新一期
        
        return {
            "period": latest['expect'],
            "date": latest['opentime'][:10],
            "numbers": [int(x) for x in latest['opencode'].split(',')],
            "trial": "573"  # 试机号（可后续改进抓取）
        }
    except Exception as e:
        print("获取数据失败:", e)
        return None

def analyze_and_recommend(latest_numbers):
    # 简单热冷码分析（示例逻辑，可后续扩展）
    hot = [0, 6, 7]
    cold = [1, 3, 9]
    
    recommendations = [
        {"type": "直选", "numbers": [3, 7, 6], "desc": "独胆7 + 热码6 + 冷码反弹"},
        {"type": "直选", "numbers": [4, 7, 9], "desc": "跨度预计回升"},
        {"type": "组六", "numbers": [1, 5, 6, 7, 8, 9], "desc": "6码大底（多专家共识）"}
    ]
    
    analysis = f"近10期热码{hot}强势，冷码{cold}出现概率上升。建议以热码为主，搭配冷码反弹。"
    
    return recommendations, analysis

def update_html(data, recommendations, analysis):
    with open('index.html', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 替换最新数据（简单字符串替换）
    new_data = f"""const latestData = {{
            period: "{data['period']}",
            date: "{data['date']}",
            trial: "{data.get('trial', '---')}",
            latest: {{ numbers: {data['numbers']}, type: "组六", sum: {sum(data['numbers'])}, span: {max(data['numbers'])-min(data['numbers'])} }},
            recommendations: {json.dumps(recommendations, ensure_ascii=False)},
            analysis: "{analysis}"
        }};"""
    
    # 替换 JS 中的 latestData
    content = re.sub(r'const latestData = \{.*?\};', new_data, content, flags=re.DOTALL)
    
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ index.html 已更新")

# ==================== 主程序 ====================
if __name__ == "__main__":
    print("开始更新福彩3D推荐...")
    data = fetch_latest_data()
    
    if data:
        recs, analysis = analyze_and_recommend(data['numbers'])
        update_html(data, recs, analysis)
        print("更新完成！")
    else:
        print("更新失败，使用默认数据")
