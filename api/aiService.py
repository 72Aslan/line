import os
import json
import re

from google import genai
from google.genai import types


def _clean_json_text(text: str) -> str:
    """
    清理 Gemini 回傳內容。

    支援：
    1. 純 JSON
    2. ```json ... ```
    3. JSON 前後有額外文字
    """

    if not text:
        raise ValueError("AI 沒有回傳內容")

    text = text.strip()

    # 移除 Markdown code block
    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    # 找第一個 { 與最後一個 }
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError(
            f"AI 回傳不是有效 JSON：{text[:300]}"
        )

    return text[start:end + 1]


def _normalize_payload(data: dict) -> dict:
    """
    統一 AI 解析結果格式。
    """

    if not isinstance(data, dict):
        raise ValueError(
            "AI 解析結果不是 JSON object"
        )

    result = {
        "date": data.get("date"),
        "time": data.get("time"),
        "location": data.get("location"),
        "level": data.get("level") or "不限",
        "fee": data.get("fee"),
        "limit_players": data.get("limit_players"),
        "shuttlecock": (
            data.get("shuttlecock")
            or "未設定"
        ),
    }

    # fee
    if result["fee"] is not None:
        try:
            result["fee"] = int(
                str(result["fee"])
                .replace(",", "")
                .replace("元", "")
                .strip()
            )
        except (
            ValueError,
            TypeError,
        ):
            result["fee"] = None

    # limit_players
    if result["limit_players"] is not None:
        try:
            result["limit_players"] = int(
                str(result["limit_players"])
                .replace("人", "")
                .strip()
            )
        except (
            ValueError,
            TypeError,
        ):
            result["limit_players"] = None

    return result


def _fallback_parse(text: str) -> dict:
    """
    Gemini 失敗時的基本解析。

    目的不是取代 AI，
    而是避免標準格式因 AI 暫時失敗而完全不能開團。
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

    # -----------------------------------------
    # 日期
    # -----------------------------------------

    date_match = re.search(
        r"(\d{1,2})\s*[\/月]\s*(\d{1,2})\s*日?",
        text,
    )

    if date_match:
        result["date"] = (
            f"{date_match.group(1)}/"
            f"{date_match.group(2)}"
        )

    # -----------------------------------------
    # 人數
    # -----------------------------------------

    players_match = re.search(
        r"(?:招收|人數|名額)?\s*"
        r"(\d{1,3})\s*人",
        text,
    )

    if players_match:
        result["limit_players"] = int(
            players_match.group(1)
        )

    # -----------------------------------------
    # 費用
    # -----------------------------------------

    fee_match = re.search(
        r"(?:費用|收費|價格)?\s*"
        r"(\d{2,5})\s*元",
        text,
    )

    if fee_match:
        result["fee"] = int(
            fee_match.group(1)
        )

    # -----------------------------------------
    # 程度
    # -----------------------------------------

    levels = [
        "初中階",
        "中高階",
        "初階",
        "中階",
        "高階",
        "不限",
    ]

    for level in levels:
        if level in text:
            result["level"] = level
            break

    # -----------------------------------------
    # 用球
    # -----------------------------------------

    if "勝利比賽級" in text:
        result["shuttlecock"] = "勝利比賽級"

    elif "勝利" in text:
        result["shuttlecock"] = "勝利"

    elif "YY" in text.upper():
        result["shuttlecock"] = "YY"

    # -----------------------------------------
    # 數字時間
    # 19:00-21:00
    # -----------------------------------------

    time_match = re.search(
        r"(\d{1,2})\s*[:：]\s*(\d{2})"
        r"\s*[-~～到至]\s*"
        r"(\d{1,2})\s*[:：]\s*(\d{2})",
        text,
    )

    if time_match:

        h1 = int(time_match.group(1))
        m1 = int(time_match.group(2))

        h2 = int(time_match.group(3))
        m2 = int(time_match.group(4))

        result["time"] = (
            f"{h1:02d}:{m1:02d}-"
            f"{h2:02d}:{m2:02d}"
        )

    else:

        # -------------------------------------
        # 中文時間
        # 晚上七點到九點
        # -------------------------------------

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
            r"(十二|十一|十|一|二|兩|三|四|五|六|七|八|九)"
            r"點"
            r"(?:到|至|~|-)"
            r"(十二|十一|十|一|二|兩|三|四|五|六|七|八|九)"
            r"點",
            text,
        )

        if zh_time_match:

            period = (
                zh_time_match.group(1)
                or ""
            )

            h1 = zh_numbers[
                zh_time_match.group(2)
            ]

            h2 = zh_numbers[
                zh_time_match.group(3)
            ]

            if period in [
                "下午",
                "晚上",
            ]:
                if h1 < 12:
                    h1 += 12

                if h2 < 12:
                    h2 += 12

            result["time"] = (
                f"{h1:02d}:00-"
                f"{h2:02d}:00"
            )

    # -----------------------------------------
    # 地點
    # -----------------------------------------

    location_match = re.search(
        r"([\u4e00-\u9fff]{2,15}"
        r"(?:運動中心|體育館|體育場|"
        r"羽球館|球館|球場))",
        text,
    )

    if location_match:
        result["location"] = (
            location_match.group(1)
        )

    return _normalize_payload(result)


def analyze_payload_with_ai(
    text: str,
) -> dict:
    """
    使用 Gemini 解析自然語言開團。

    Gemini 成功：
        回傳 AI 解析結果

    Gemini 失敗：
        使用 fallback parser
    """

    api_key = (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
    )

    # -----------------------------------------
    # 沒有 API Key
    # -----------------------------------------

    if not api_key:

        print(
            "[AI WARNING] "
            "GEMINI_API_KEY is not set. "
            "Using fallback parser."
        )

        return _fallback_parse(text)

    prompt = f"""
你是一個羽球團務 AI。

請從以下使用者訊息中提取開團資訊。

使用者訊息：
{text}

只回傳 JSON object。
不要 Markdown。
不要 ```json。
不要解釋。

JSON 格式：

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
2. 「8/15」轉成「8/15」。
3. fee 必須是整數。
4. limit_players 必須是整數。
5. 不確定的欄位填 null。
6. 地點只保留場地名稱。
"""

    try:

        client = genai.Client(
            api_key=api_key
        )

        response = (
            client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
        )

        raw_text = (
            response.text
            if response.text
            else ""
        )

        cleaned = _clean_json_text(
            raw_text
        )

        data = json.loads(cleaned)

        result = _normalize_payload(data)

        print(
            "[AI RESULT]",
            result,
        )

        return result

    except Exception as e:

        print(
            "[AI WARNING] Gemini failed:",
            type(e).__name__,
            str(e),
        )

        print(
            "[AI] Using fallback parser."
        )

        return _fallback_parse(text)
