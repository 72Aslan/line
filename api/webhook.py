import os
import sys
from urllib.parse import parse_qs

from flask import Flask, request

# ==================================================
# Path
# ==================================================

current_dir = os.path.dirname(
    os.path.abspath(__file__)
)

parent_dir = os.path.dirname(
    current_dir
)

for directory in [
    current_dir,
    parent_dir,
]:
    if directory not in sys.path:
        sys.path.insert(
            0,
            directory,
        )


# ==================================================
# LINE SDK
# ==================================================

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


# ==================================================
# Flex
# ==================================================

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


# ==================================================
# Lazy AI
# ==================================================

def _get_analyze_payload_with_ai():

    try:
        from api.aiService import (
            analyze_payload_with_ai
        )

    except ModuleNotFoundError:

        from aiService import (
            analyze_payload_with_ai
        )

    return analyze_payload_with_ai


# ==================================================
# Lazy DB
# ==================================================

def _get_db():

    try:
        from api import db

    except ModuleNotFoundError:

        import db

    return db


# ==================================================
# Flask
# ==================================================

app = Flask(__name__)


# ==================================================
# LINE Config
# ==================================================

channel_secret = os.getenv(
    "LINE_CHANNEL_SECRET",
    "",
)

channel_access_token = os.getenv(
    "LINE_CHANNEL_ACCESS_TOKEN",
    "",
)


configuration = Configuration(
    access_token=channel_access_token
)


handler = (
    WebhookHandler(channel_secret)
    if channel_secret
    else None
)


# ==================================================
# Helpers
# ==================================================

def _get_user_id(event):

    return getattr(
        event.source,
        "user_id",
        None,
    )


def _reply_text(
    reply_token,
    text,
):

    with ApiClient(
        configuration
    ) as api_client:

        MessagingApi(
            api_client
        ).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    TextMessage(
                        text=text
                    )
                ],
            )
        )


def _reply_flex(
    reply_token,
    alt_text,
    contents,
):

    with ApiClient(
        configuration
    ) as api_client:

        MessagingApi(
            api_client
        ).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[
                    FlexMessage(
                        alt_text=alt_text,
                        contents=FlexContainer.from_dict(
                            contents
                        ),
                    )
                ],
            )
        )


# ==================================================
# Webhook
# ==================================================

@app.route(
    "/",
    methods=["GET", "POST"],
)
@app.route(
    "/api/webhook",
    methods=["GET", "POST"],
)
def webhook():

    if request.method == "GET":

        return (
            "LINE Bot Server Ready!",
            200,
        )

    signature = request.headers.get(
        "X-Line-Signature",
        "",
    )

    body = request.get_data(
        as_text=True
    )

    if not handler:

        return "OK", 200

    try:

        handler.handle(
            body,
            signature,
        )

    except Exception as e:

        print(
            "[WEBHOOK ERROR]",
            type(e).__name__,
            str(e),
        )

        # LINE webhook 必須回 200
        return "OK", 200

    return "OK", 200


# ==================================================
# Event Handlers
# ==================================================

if handler:

    # ==================================================
    # Message
    # ==================================================

    @handler.add(
        MessageEvent,
        message=TextMessageContent,
    )
    def handle_message(event):

        user_text = (
            event.message.text.strip()
        )

        user_id = _get_user_id(
            event
        )

        # ==================================================
        # 查球局
        # ==================================================

        if user_text in [
            "查球局",
            "查看場次資訊",
            "目前球局",
            "有球局嗎",
        ]:

            try:

                db = _get_db()

                active_event = (
                    db.get_latest_open_event()
                )

                if not active_event:

                    _reply_text(
                        event.reply_token,
                        "目前沒有進行中的球局唷。\n"
                        "你可以輸入「我要開團」建立一場。",
                    )

                    return

                registered_count = (
                    db.count_registered(
                        active_event["id"]
                    )
                )

                join_contents = (
                    generate_join_card(
                        event_id=active_event["id"],
                        date=(
                            active_event.get(
                                "date_text"
                            )
                            or "未定"
                        ),
                        location=(
                            active_event.get(
                                "location"
                            )
                            or "未定"
                        ),
                        time=(
                            active_event.get(
                                "time_text"
                            )
                            or "未定"
                        ),
                        level=(
                            active_event.get(
                                "level"
                            )
                            or "不限"
                        ),
                        fee=(
                            active_event.get(
                                "fee"
                            )
                            or 0
                        ),
                        current=registered_count,
                        limit=(
                            active_event.get(
                                "limit_players"
                            )
                            or 0
                        ),
                    )
                )

                alt_text = (
                    f"{active_event.get('date_text')}"
                    f" "
                    f"{active_event.get('location')}"
                    f" 羽球團"
                )

                _reply_flex(
                    event.reply_token,
                    alt_text,
                    join_contents,
                )

            except Exception as e:

                print(
                    "[QUERY EVENT ERROR]",
                    type(e).__name__,
                    str(e),
                )

                _reply_text(
                    event.reply_token,
                    "查詢球局時發生錯誤。\n\n"
                    f"{type(e).__name__}: "
                    f"{str(e)[:300]}",
                )

            return

        # ==================================================
        # 開團 Intent
        # ==================================================

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

            # ----------------------------------------------
            # LINE user id
            # ----------------------------------------------

            if not user_id:

                _reply_text(
                    event.reply_token,
                    "請先加官方帳號好友，"
                    "才能幫你建立場次唷。",
                )

                return

            # ----------------------------------------------
            # 只有「我要開團」
            # ----------------------------------------------

            short_commands = [
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

            if user_text in short_commands:

                _reply_text(
                    event.reply_token,
                    "可以！請把開團資訊告訴我，例如：\n\n"
                    "開團，8/15 晚上七點到九點，"
                    "中山運動中心，6人，250元，"
                    "初中階，用勝利比賽級",
                )

                return

            # ----------------------------------------------
            # 完整開團
            # ----------------------------------------------

            # STEP 1：AI
            try:

                analyze_payload_with_ai = (
                    _get_analyze_payload_with_ai()
                )

                match_data = (
                    analyze_payload_with_ai(
                        user_text
                    )
                )

                print(
                    "[CREATE EVENT] AI RESULT:",
                    match_data,
                )

            except Exception as e:

                print(
                    "[CREATE EVENT] "
                    "STEP 1 AI ERROR:",
                    type(e).__name__,
                    str(e),
                )

                _reply_text(
                    event.reply_token,
                    "❌ 開團失敗：AI 解析錯誤\n\n"
                    f"{type(e).__name__}: "
                    f"{str(e)[:300]}",
                )

                return

            # ----------------------------------------------
            # STEP 2：必要欄位
            # ----------------------------------------------

            missing = []

            if not match_data.get(
                "date"
            ):
                missing.append(
                    "日期"
                )

            if not match_data.get(
                "time"
            ):
                missing.append(
                    "時間"
                )

            if not match_data.get(
                "location"
            ):
                missing.append(
                    "場地"
                )

            if not match_data.get(
                "limit_players"
            ):
                missing.append(
                    "人數"
                )

            if missing:

                _reply_text(
                    event.reply_token,
                    "我還缺少這些資訊："
                    + "、".join(missing)
                    + "\n\n例如：\n"
                    "開團，8/15 晚上七點到九點，"
                    "中山運動中心，6人，250元，"
                    "初中階，用勝利比賽級",
                )

                return

            # ----------------------------------------------
            # STEP 3：DB
            # ----------------------------------------------

            try:

                db = _get_db()

                draft_event = (
                    db.create_draft_event(
                        user_id,
                        match_data,
                    )
                )

                print(
                    "[CREATE EVENT] "
                    "DB RESULT:",
                    draft_event,
                )

            except Exception as e:

                print(
                    "[CREATE EVENT] "
                    "STEP 3 DB ERROR:",
                    type(e).__name__,
                    str(e),
                )

                _reply_text(
                    event.reply_token,
                    "❌ 開團失敗：資料庫錯誤\n\n"
                    f"{type(e).__name__}: "
                    f"{str(e)[:300]}",
                )

                return

            # ----------------------------------------------
            # STEP 4：Flex
            # ----------------------------------------------

            try:

                flex_contents = (
                    generate_flex_message(
                        match_data,
                        draft_event["id"],
                    )
                )

                print(
                    "[CREATE EVENT] "
                    "FLEX RESULT OK"
                )

            except Exception as e:

                print(
                    "[CREATE EVENT] "
                    "STEP 4 FLEX ERROR:",
                    type(e).__name__,
                    str(e),
                )

                _reply_text(
                    event.reply_token,
                    "❌ 開團失敗："
                    "Flex 卡片建立錯誤\n\n"
                    f"{type(e).__name__}: "
                    f"{str(e)[:300]}",
                )

                return

            # ----------------------------------------------
            # STEP 5：送 LINE
            # ----------------------------------------------

            try:

                _reply_flex(
                    event.reply_token,
                    "請確認開團資訊",
                    flex_contents,
                )

            except Exception as e:

                print(
                    "[CREATE EVENT] "
                    "STEP 5 LINE ERROR:",
                    type(e).__name__,
                    str(e),
                )

                return

            return

        # ==================================================
        # 一般訊息
        # ==================================================

        _reply_text(
            event.reply_token,
            f"收到你的訊息：{user_text}",
        )

    # ==================================================
    # Postback
    # ==================================================

    @handler.add(
        PostbackEvent
    )
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

        user_id = _get_user_id(
            event
        )

        if not user_id:

            _reply_text(
                event.reply_token,
                "請先加官方帳號好友，"
                "才能幫你處理報名資料唷。",
            )

            return

        # ----------------------------------------------
        # DB
        # ----------------------------------------------

        try:

            db = _get_db()

        except Exception as e:

            print(
                "[POSTBACK DB ERROR]",
                type(e).__name__,
                str(e),
            )

            _reply_text(
                event.reply_token,
                "資料庫連線失敗。\n\n"
                f"{type(e).__name__}: "
                f"{str(e)[:300]}",
            )

            return

        # ==================================================
        # 確認開團
        # ==================================================

        if (
            action == "confirm"
            and event_id
        ):

            try:

                confirmed = (
                    db.confirm_event(
                        event_id,
                        user_id,
                    )
                )

            except Exception as e:

                print(
                    "[CONFIRM EVENT ERROR]",
                    type(e).__name__,
                    str(e),
                )

                _reply_text(
                    event.reply_token,
                    "❌ 確認開團失敗。\n\n"
                    f"{type(e).__name__}: "
                    f"{str(e)[:300]}",
                )

                return

            if not confirmed:

                _reply_text(
                    event.reply_token,
                    "這場球局不存在、"
                    "已經確認過，"
                    "或你不是這場球局的團主。",
                )

                return

            try:

                success_contents = (
                    generate_success_card(
                        date=(
                            confirmed.get(
                                "date_text"
                            )
                            or "未定"
                        ),
                        location=(
                            confirmed.get(
                                "location"
                            )
                            or "未定"
                        ),
                        time=(
                            confirmed.get(
                                "time_text"
                            )
                            or "未定"
                        ),
                        limit=str(
                            confirmed.get(
                                "limit_players"
                            )
                            or 0
                        ),
                    )
                )

                _reply_flex(
                    event.reply_token,
                    "🎉 開團成功！",
                    success_contents,
                )

            except Exception as e:

                print(
                    "[SUCCESS FLEX ERROR]",
                    type(e).__name__,
                    str(e),
                )

                _reply_text(
                    event.reply_token,
                    "開團已建立成功，"
                    "但成功卡片產生失敗。\n\n"
                    f"{type(e).__name__}: "
                    f"{str(e)[:300]}",
                )

            return

        # ==================================================
        # +1 報名
        # ==================================================

        if (
            action == "join_event"
            and event_id
        ):

            try:

                result = (
                    db.create_registration(
                        event_id,
                        user_id,
                    )
                )

            except ValueError as e:

                _reply_text(
                    event.reply_token,
                    str(e),
                )

                return

            except Exception as e:

                print(
                    "[JOIN EVENT ERROR]",
                    type(e).__name__,
                    str(e),
                )

                _reply_text(
                    event.reply_token,
                    "❌ 報名時發生錯誤。\n\n"
                    f"{type(e).__name__}: "
                    f"{str(e)[:300]}",
                )

                return

            limit = result[
                "limit"
            ]

            position = result[
                "position_number"
            ]

            # ----------------------------------------------
            # 已經報名
            # ----------------------------------------------

            if result[
                "already_registered"
            ]:

                status_label = (
                    "正取"
                    if result["status"]
                    == "registered"
                    else "候補"
                )

                msg = (
                    "你已經在名單裡囉！\n"
                    f"（{status_label}"
                    f"第 {position} 位）"
                )

            # ----------------------------------------------
            # 正取
            # ----------------------------------------------

            elif (
                result["status"]
                == "registered"
            ):

                msg = (
                    "✅ 報名成功！\n"
                    f"目前順位：第 "
                    f"{position} 位\n"
                    f"場次人數："
                    f"{position}/{limit}"
                )

            # ----------------------------------------------
            # 候補
            # ----------------------------------------------

            else:

                msg = (
                    "⚠️ 目前正式名額已滿！\n"
                    f"已為你安排候補順位："
                    f"第 {position} 位"
                )

            _reply_text(
                event.reply_token,
                msg,
            )

            return

        # ==================================================
        # Unknown Postback
        # ==================================================

        _reply_text(
            event.reply_token,
            "這個按鈕的資料格式有點問題，"
            "請重新操作一次。",
        )
