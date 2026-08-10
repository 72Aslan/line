import os
import json
import re
from google import genai
from google.genai import types

def analyze_payload_with_ai(text: str) -> dict:
    """
    使用 Gemini 2.5 Flash 解析使用者的自然語言開團訊息
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("AI Error: GEMINI_API_KEY is not set.")
        raise ValueError("GEMINI_API_KEY Missing")

    # 初始化 Client
    client = genai.Client(api_key=api_key)

    prompt = f"""
    你是一個羽球報名小幫手。請從以下使用者的開團訊息中提取資訊，並嚴格只回傳一個標準 JSON 物件，不要有任何 Markdown 標籤或多餘文字。

    待解析訊息："{text}"

    JSON 必須包含以下欄位：
    - "date": 日期 (例如 "8/15")
    - "time": 時間 (例如 "19:00-21:00")
    - "location": 地點 (例如 "中山運動中心")
    - "level": 程度 (例如 "初中階"，若未提及則回傳 "不限")
    - "fee": 費用數字 (例如 250，整數)
    - "limit_players": 招收人數數字 (例如 6，整數)
    - "shuttlecock": 用球 (例如 "勝利比賽級"，若未提及則回傳 "未設定")
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json", # 強制要求回傳 JSON 格式
                temperature=0.1
            )
        )

        res_text = response.text.strip()
        # 清理可能夾帶的 ```json ... ``` 包裹標籤
        res_text = re.sub(r'^
http://googleusercontent.com/immersive_entry_chip/0

---

### 🔑 防呆排查：檢查 Vercel 的 API Key

1. 前往 Vercel 專案 ➔ **`Settings`** ➔ **`Environment Variables`**。
2. 確認是否有新增名稱為 **`GEMINI_API_KEY`** 的環境變數，且其 Value 為有效的 Google Gemini API Key。
3. 若先前忘記新增，新增後請重新做一次 **`Redeploy`**（重新部署），變數才會真正生效。

---

### 🏃‍♂️ 驗證步驟

1. 提交 `api/aiService.py` 的更新並 Commit 到 GitHub。
2. 確認 Vercel 綠燈 🟢 **Ready**。
3. 至 LINE 聊天室發送：
   > **`開團，8/15 晚上七點到九點，中山運動中心，6人，250元，初中階，用勝利比賽級`**

更新後，Gemini 就會順利抓取內容並彈出「請確認開團資訊」的確認卡片囉！
