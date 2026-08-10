import os
import json
from google import genai
from google.genai import types

# 不要在模組最上層就建立 client！
# 這樣每次 import 這個檔案（包含每一次 webhook 請求）都會觸發 genai.Client() 的
# 憑證探測，若沒設好 GEMINI_API_KEY 或探測過程卡住，就會拖慢每一次回應。
_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY 環境變數未設定，請至 Vercel 專案設定新增。")
        _client = genai.Client(api_key=api_key)
    return _client


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

    response = _get_client().models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )

    return json.loads(response.text)
