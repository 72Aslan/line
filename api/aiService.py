import os
import json
import re
from google import genai
from google.genai import types


def _clean_json_text(text: str) -> str:
    """清理 Gemini 可能回傳的 Markdown JSON。"""
    if not text:
        raise ValueError("AI 沒有回傳內容")

    text = text.strip()

    # 移除 ```json ... ``` 或 ``` ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)

    # 找出第一個 JSON object
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"AI 回傳不是有效 JSON：{text[:300]}")

    return text[start:end + 1]


def _normalize_payload(data: dict) -> dict:
    """統一 AI / fallback 的資料格式。"""

    if not isinstance(data, dict):
        raise ValueError("解析結果不是 JSON object")

    result = {
        "date": data.get("date"),
        "time": data.get("time"),
        "location": data.get("location"),
        "level": data.get("level") or "不限",
        "fee": data.get("fee"),
        "limit_players": data.get("limit_players"),
        "shuttlecock": data.get("shuttlecock") or "未設定",
    }

    # 數字欄位轉 int
    for key in ["fee", "limit_players"]:
        value = result.get(key)

        if value is not None:
            try:
                result[key] = int(str(value).replace(",", "").replace("元", "").strip())
            except (ValueError, TypeError):
                result[key] = None

    return result


def _fallback_parse(text: str) -> dict:
    """
    Gemini 無法使用時的基本中文格式解析。
    主要保證 MVP 測試格式可以正常建立場次。
    """

    result = {
        "date": None,
        "time": None,
        "location": None,
        "level": "不限",
        "fee": None,
        "limit_players": None,
        "shuttlecock": "未設定",
    }

    # 日期，例如：
    # 8/15
    # 8月15日
    date_match = re.search(
        r"(\d{1,2})\s*[\/月]\s*(\d{1,2})\s*日?",
        text
    )

    if date_match:
        result["date"] = f"{date_match.group(1)}/{date_match.group(2)}"

    # 人數，例如：
    # 6人
    # 6 人
    # 招收6人
    players_match = re.search(
        r"(?:招收|人數|名額)?\s*(\d{1,3})\s*人",
        text
    )

    if players_match:
        result["limit_players"] = int(players_match.group(1))

    # 費用，例如：
    # 250元
    # 250 元
    # 250
    fee_match = re.search(
        r"(?:費用|收費|價格)?\s*(\d{2,5})\s*元",
        text
    )

    if fee_match:
        result["fee"] = int(fee_match.group(1))

    # 程度
    level_keywords = [
        "初中階",
        "初階",
        "中階",
        "中高階",
        "高階",
        "不限",
    ]

    for level in level_keywords:
        if level in text:
            result["level"] = level
            break

    # 用球
    if "勝利比賽級" in text:
        result["shuttlecock"] = "勝利比賽級"
    elif "勝利" in text:
        result["shuttlecock"] = "勝利"
    elif "YY" in text.upper():
        result["shuttlecock"] = "YY"

    # 時間
    # 19:00-21:00
    time_match = re.search(
        r"(\d{1,2})\s*[:：]\s*(\d{2})\s*[-~～到至]\s*(\d{1,2})\s*[:：]\s*(\d{2})",
        text
    )

    if time_match:
        h1 = int(time_match.group(1))
        m1 = int(time_match.group(2))
        h2 = int(time_match.group(3))
        m2 = int(time_match.group(4))

        result["time"] = f"{h1:02d}:{m1:02d}-{h2:02d}:{m2:02d}"

    else:
        # 晚上七點到九點
        zh_numbers = {
            "一": 1,
            "二": 2,
            "兩": 2,
            "三": 3,
            "四": 4,
            "五": 5,
            "六": 6,
            "七": 7,
            "八": 8,
            "九": 9,
            "十": 10,
            "十一": 11,
            "十二": 12,
        }

        zh_time_match = re.search(
            r"(早上|上午|中午|下午|晚上)?"
            r"(一|二|兩|三|四|五|六|七|八|九|十|十一|十二)"
            r"點"
            r"(?:到|至|~|-)"
            r"(一|二|兩|三|四|五|六|七|八|九|十|十一|十二)"
            r"點",
            text
        )

        if zh_time_match:
            period = zh_time_match.group(1) or ""
            h1 = zh_numbers[zh_time_match.group(2)]
            h2 = zh_numbers[zh_time_match.group(3)]

            if period in ("下午", "晚上"):
                if h1 < 12:
                    h1 += 12
                if h2 < 12:
                    h2 += 12

            result["time"] = f"{h1:02d}:00-{h2:02d}:00"

    # 地點
    location_match = re.search(
        r"(?:到|在|地點[：:]?|場地[：:]?)\s*"
        r"([^，。,.\s]+(?:運動中心|體育館|體育場|羽球館|球館|球場))",
        text
    )

    if location_match:
        result["location"] = location_match.group(1)
    else:
        # 常見「中山運動中心」
        location_match = re.search(
            r"([\u4e00-\u9fff]{2,12}(?:運動中心|體育館|羽球館|球館|球場))",
            text
        )

        if location_match:
            result["location"] = location_match.group(1)

    return _normalize_payload(result)


def analyze_payload_with_ai(text: str) -> dict:
    """
    使用 Gemini 解析自然語言開團。
    若 AI 失敗，使用 fallback parser。
    """

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    prompt = f"""
你是一個羽球團務 AI。

請從以下使用者訊息中提取開團資訊。

使用者訊息：
{text}

只回傳 JSON object，不要 Markdown，不要解釋。

JSON 欄位：

{{
  "date": "日期，例如 8/15",
  "time": "時間，例如 19:00-21:00",
  "location": "場地名稱",
  "level": "程度，例如 初中階；沒有就填 不限",
  "fee": 250,
  "limit_players": 6,
  "shuttlecock": "用球；沒有就填 未設定"
}}

規則：

1. 「晚上七點到九點」轉成「19:00-21:00」。
2. 「下午七點」不合理時，依語意判斷。
3. fee 必須是整數。
4. limit_players 必須是整數。
5. 不確定的欄位填 null。
"""

    # 有 API Key 才呼叫 Gemini
    if api_key:
        try:
            client = genai.Client(api_key=api_key)

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )

            raw = response.text or ""
            cleaned = _clean_json_text(raw)

            data = json.loads(cleaned)
            result = _normalize_payload(data)

            # AI 結果至少要能判斷出基本欄位
            if result.get("limit_players") or result.get("location"):
                return result

        except Exception as e:
            print(f"[AI WARNING] Gemini parsing failed: {type(e).__name__}: {e}")

    # Gemini 不可用 / JSON 壞掉 → fallback
    result = _fallback_parse(text)

    print(f"[AI FALLBACK] {result}")

    return result
