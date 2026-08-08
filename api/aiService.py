import os
import json
from openai import OpenAI

# 初始 OpenAI 客戶端，會自動讀取環境變數 OPENAI_API_KEY
client = OpenAI()

def analyze_payload_with_ai(text):
    prompt = f"""
    你是一個羽球開團小幫手的後端解析器。請從使用者的訊息中精確擷取欄位，嚴格回傳 JSON 格式：
    - date: 日期 (例如 "8/15")
    - time: 時間 (例如 "19:00-21:00")
    - location: 地點 (例如 "中山運動中心")
    - limit_players: 招收人數數字 (例如 6)
    - fee: 費用數字 (例如 250)
    - level: 程度 (例如 "初中階")
    - shuttlecock: 用球 (例如 "勝利比賽級")

    使用者訊息：「{text}」
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}  # 強制輸出 JSON
    )

    # 將 AI 回傳的字串轉換為 Python 字典 (Dict)
    return json.loads(response.choices[0].message.content)