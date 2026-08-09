import os
import json
from google import genai
from google.genai import types

# 不要在模組最上層就建立 client！
# 這樣每次 import 這個檔案（包含每一次 webhook 請求、甚至 LINE 的 Verify 測試）
# 都會觸發 genai.Client() 的憑證探測，若沒設好 GEMINI_API_KEY 或探測過程卡住，
# 就會拖慢每一次回應，導致超過 LINE 要求的 2 秒回應時限而 timeout。
_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY 環境變數未設定，請至 Vercel 專案設定新增。")
        # 明確傳入 api_key，避免 SDK 嘗試自動探測憑證（ADC 等）而卡住
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

    # 使用免費又快速的 gemini-2.5-flash 模型
    response = _get_client().models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",  # 強制要求回傳 JSON
        ),
    )

    # 將 Gemini 回傳的 JSON 字串轉換為 Python 字典 (Dict)
    return json.loads(response.text)
