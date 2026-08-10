import os
import sys
from urllib.parse import parse_qs

from flask import Flask, request

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

for d in [current_dir, parent_dir]:
    if d not in sys.path:
        sys.path.insert(0, d)

from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    FlexContainer,
    FlexMessage,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import (
    MessageEvent,
    PostbackEvent,
    TextMessageContent,
)

try:
    from api.flexTemplates import (
        generate_flex_message,
        generate_join_card,
        generate_success_card,
    )
except ModuleNotFoundError:
    from flexTemplates import (
        generate_flex_message,
        generate_join_card,
        generate_success_card,
    )


def _get_analyze_payload_with_ai():
    try:
        from api.aiService import analyze_payload_with_ai
    except ModuleNotFoundError:
        from aiService import analyze_payload_with_ai

    return analyze_payload_with_ai


def _get_db():
    try:
        from api import db
    except ModuleNotFoundError:
        import db

    return db


app = Flask(__name__)

channel_secret = os.getenv("LINE_CHANNEL_SECRET", "")
channel_access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")

configuration = Configuration(
    access_token=channel_access_token
)

handler = WebhookHandler(channel_secret) if channel_secret else None


def _get_user_id(event):
    return getattr(event.source, "user_id", None)


def _reply_text(reply_token, text):
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    TextMessage(text=text)
                ],
            )
        )


def _reply_flex(reply_token, alt_text, contents):
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    FlexMessage(
                        alt_text=alt_text,
                        contents=FlexContainer.from_dict(contents),
                    )
                ],
            )
        )


@app.route("/", methods=["GET", "POST"])
@app.route("/api/webhook", methods=["GET", "POST"])
def webhook():

    if request.method == "GET":
        return "LINE Bot Server Ready!", 200

    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    if not handler:
        return "OK", 200

    try:
        handler.handle(body, signature)

    except Exception as e:
        print(
            f"[WEBHOOK ERROR] "
            f"{type(e).__name__}: {e}"
        )

        # LINE webhook 必須正常回 200
        return "OK", 200

    return "OK", 200


if handler:

    @handler.add(
        MessageEvent,
        message=TextMessageContent,
    )
    def handle_message(event):

        user_text = event.message.text.strip()
        user_id = _get_user_id(event)

        # -----------------------------------------
        # 查球局
        # -----------------------------------------

        if user_text in [
            "查球局",
            "查看場次資訊",
            "目前球局",
            "有球局嗎",
        ]:

            try:
                db = _get_db()

                active_event = db.get_latest_open_event()

                if not active_event:
                    _reply_text(
                        event.reply_token,
                        "目前沒有進行中的球局唷。\n"
                        "你可以輸入「我要開團」建立一場。",
                    )
                    return

                registered_count = db.count_registered(
                    active_event["id"]
                )

                join_contents = generate_join_card(
                    event_id=active_event["id"],
                    date=active_event.get("date_text") or "未定",
                    location=active_event.get("location") or "未定",
                    time=active_event.get("time_text") or "未定",
                    level=active_event.get("level") or "不限",
                    fee=active_event.get("fee") or 0,
                    current=registered_count,
                    limit=active_event.get("limit_players") or 0,
                )

                alt_text = (
                    f"{active_event.get('date_text')} "
                    f"{active_event.get('location')} 羽球團"
                )

                _reply_flex(
                    event.reply_token,
                    alt_text,
                    join_contents,
                )

            except Exception as e:
                print(
                    f"[QUERY EVENT ERROR] "
                    f"{type(e).__name__}: {e}"
                )

                _reply_text(
                    event.reply_token,
                    "目前查詢球局時發生錯誤，請稍後再試。",
                )

            return

        # -----------------------------------------
        # 開團 Intent
        # -----------------------------------------

        open_event_triggers = [
            "開團",
            "我要開團",
            "我想開團",
            "幫我開團",
            "幫我開一團",
            "開一團",
            "建立球局",
            "建立一場",
            "建立羽球團",
        ]

        is_open_event = any(
            trigger in user_text
            for trigger in open_event_triggers
        )

        if is_open_event:

            if not user_id:
                _reply_text(
                    event.reply_token,
                    "請先加官方帳號好友，"
                    "才能幫你建立場次唷。",
                )
                return

            # 如果只是說「我要開團」
            # 還沒有提供任何場次資訊
            short_command = user_text in [
                "開團",
                "我要開團",
                "我想開團",
                "幫我開團",
                "幫我開一團",
                "開一團",
                "建立球局",
                "建立一場",
                "建立羽球團",
            ]

            if short_command:

                _reply_text(
                    event.reply_token,
                    "可以！請把開團資訊告訴我，例如：\n\n"
                    "開團，8/15 晚上七點到九點，"
                    "中山運動中心，6人，250元，"
                    "初中階，用勝利比賽級",
                )

                return

            try:

                analyze_payload_with_ai = (
                    _get_analyze_payload_with_ai()
                )

                match_data = analyze_payload_with_ai(
                    user_text
                )

                # 必要欄位檢查
                missing = []

                if not match_data.get("date"):
                    missing.append("日期")

                if not match_data.get("time"):
                    missing.append("時間")

                if not match_data.get("location"):
                    missing.append("場地")

                if not match_data.get("limit_players"):
                    missing.append("人數")

                if missing:

                    _reply_text(
                        event.reply_token,
                        "我還缺少這些資訊："
                        + "、".join(missing)
                        + "\n\n例如：\n"
                        "開團，8/15 晚上七點到九點，"
                        "中山運動中心，6人，250元，初中階",
                    )

                    return

                db = _get_db()

                draft_event = db.create_draft_event(
                    user_id,
                    match_data,
                )

                flex_contents = generate_flex_message(
                    match_data,
                    draft_event["id"],
                )

                _reply_flex(
                    event.reply_token,
                    "請確認開團資訊",
                    flex_contents,
                )

            except Exception as e:

                print(
                    f"[AI/CREATE EVENT ERROR] "
                    f"{type(e).__name__}: {e}"
                )

                _reply_text(
                    event.reply_token,
                    "開團時發生錯誤。\n"
                    "請稍後再試一次。",
                )

            return

        # -----------------------------------------
        # 一般訊息
        # -----------------------------------------

        _reply_text(
            event.reply_token,
            f"收到你的訊息：{user_text}",
        )


    # -----------------------------------------
    # Postback
    # -----------------------------------------

    @handler.add(PostbackEvent)
    def handle_postback(event):

        params = parse_qs(
            event.postback.data
        )

        action = params.get(
            "action",
            [None],
        )[0]

        event_id = params.get(
            "event_id",
            [None],
        )[0]

        user_id = _get_user_id(event)

        db = _get_db()

        if not user_id:
            _reply_text(
                event.reply_token,
                "請先加官方帳號好友，"
                "才能幫你處理報名資料唷。",
            )
            return

        # -----------------------------------------
        # 確認開團
        # -----------------------------------------

        if action == "confirm" and event_id:

            try:

                confirmed = db.confirm_event(
                    event_id,
                    user_id,
                )

                if not confirmed:

                    _reply_text(
                        event.reply_token,
                        "這場開團不存在、"
                        "已經確認過，"
                        "或你不是這場的團主。",
                    )

                    return

                success_contents = generate_success_card(
                    date=confirmed.get("date_text") or "未定",
                    location=confirmed.get("location") or "未定",
                    time=confirmed.get("time_text") or "未定",
                    limit=str(
                        confirmed.get("limit_players") or 0
                    ),
                )

                _reply_flex(
                    event.reply_token,
                    "🎉 開團成功！",
                    success_contents,
                )

            except Exception as e:

                print(
                    f"[CONFIRM EVENT ERROR] "
                    f"{type(e).__name__}: {e}"
                )

                _reply_text(
                    event.reply_token,
                    "確認開團時發生錯誤，"
                    "請稍後再試。",
                )

            return

        # -----------------------------------------
        # +1 報名
        # -----------------------------------------

        if action == "join_event" and event_id:

            try:

                result = db.create_registration(
                    event_id,
                    user_id,
                )

            except ValueError as e:

                _reply_text(
                    event.reply_token,
                    str(e),
                )

                return

            except Exception as e:

                print(
                    f"[JOIN EVENT ERROR] "
                    f"{type(e).__name__}: {e}"
                )

                _reply_text(
                    event.reply_token,
                    "報名時發生錯誤，"
                    "請稍後再試。",
                )

                return

            limit = result["limit"]
            position = result["position_number"]

            if result["already_registered"]:

                status_label = (
                    "正取"
                    if result["status"] == "registered"
                    else "候補"
                )

                msg = (
                    "你已經在名單裡囉！"
                    f"\n（{status_label}第 {position} 位）"
                )

            elif result["status"] == "registered":

                msg = (
                    "✅ 報名成功！\n"
                    f"目前順位：第 {position} 位\n"
                    f"場次人數：{position}/{limit}"
                )

            else:

                msg = (
                    "⚠️ 目前正式名額已滿！\n"
                    f"已為你安排候補順位：第 {position} 位"
                )

            _reply_text(
                event.reply_token,
                msg,
            )

            return

        _reply_text(
            event.reply_token,
            "這個按鈕的資料格式有點問題，"
            "請重新操作一次。",
        )
