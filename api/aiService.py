import os
import json
from google import genai
from google.genai import types

# 初始化 Gemini 客戶端，會自動讀取你設定的 GEMINI_API_KEY 環境變數
client = genai.Client()

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

    # 使用免費又快速的 gemini-2.5-flash 模型
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json", # 強制要求回傳 JSON
        ),
    )

    # 將 Gemini 回傳的 JSON 字串轉換為 Python 字典 (Dict)
    return json.loads(response.text)
