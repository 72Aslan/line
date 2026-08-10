import os
import sys
from urllib.parse import parse_qs

from flask import Flask, request

# 確保當前目錄與上層目錄都在 sys.path 中，防範 Vercel 路徑迷路
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
for d in [current_dir, parent_dir]:
    if d not in sys.path:
        sys.path.insert(0, d)

from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    ApiClient, Configuration, FlexContainer, FlexMessage, MessagingApi,
    ReplyMessageRequest, TextMessage,
)
from linebot.v3.webhooks import MessageEvent, PostbackEvent, TextMessageContent

# flexTemplates 很輕量，直接載入沒關係
try:
    from api.flexTemplates import generate_flex_message, generate_join_card, generate_success_card
except ModuleNotFoundError:
    from flexTemplates import generate_flex_message, generate_join_card, generate_success_card

# aiService 會載入 google-genai SDK，屬於較重的依賴，延後到真的需要 AI 解析時才 import
def _get_analyze_payload_with_ai():
    try:
        from api.aiService import analyze_payload_with_ai
    except ModuleNotFoundError:
        from aiService import analyze_payload_with_ai
    return analyze_payload_with_ai


# db 會建立 Supabase client，同樣延後到真的需要查資料庫時才 import + 建立連線
def _get_db():
    try:
        from api import db
    except ModuleNotFoundError:
        import db
    return db


app = Flask(__name__)

channel_secret = os.getenv('LINE_CHANNEL_SECRET', '')
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', '')

configuration = Configuration(access_token=channel_access_token)
handler = WebhookHandler(channel_secret) if channel_secret else None


def _get_user_id(event):
    """取得傳訊息的人的 LINE user id（用來寫入報名資料、之後 push 通知用）。"""
    return getattr(event.source, "user_id", None)


def _reply_text(reply_token, text):
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=text)])
        )


def _reply_flex(reply_token, alt_text, contents):
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[FlexMessage(alt_text=alt_text, contents=FlexContainer.from_dict(contents))],
            )
        )


@app.route("/", methods=['GET', 'POST'])
@app.route("/api/webhook", methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        return 'LINE Bot Server Ready!', 200

    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)

    if not handler:
        return 'OK', 200

    try:
        handler.handle(body, signature)
    except Exception as e:
        # 強制捕捉所有例外並回傳 200，確保 LINE Verify 絕對能通過，
        # 真正的錯誤請看 Vercel Runtime Logs
        print(f"Webhook Exception caught: {e}")
        return 'OK', 200

    return 'OK', 200


# ------------------ 訊息處理區塊 ------------------
if handler:

    @handler.add(MessageEvent, message=TextMessageContent)
    def handle_message(event):
        user_text = event.message.text.strip()
        user_id = _get_user_id(event)
        db = _get_db()

        # 查球局
        if user_text in ["查球局", "查看場次資訊"]:
            active_event = db.get_latest_open_event()
            if not active_event:
                _reply_text(event.reply_token, "目前沒有進行中的球局唷，輸入「開團」建立一場吧！")
                return

            registered_count = db.count_registered(active_event["id"])
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
            alt_text = f"{active_event.get('date_text')} {active_event.get('location')} 羽球團"
            _reply_flex(event.reply_token, alt_text, join_contents)
            return

        # 自然語言開團
        if user_text.startswith('開團'):
            if not user_id:
                _reply_text(event.reply_token, "請先加官方帳號好友，才能幫你建立場次唷。")
                return
            try:
                analyze_payload_with_ai = _get_analyze_payload_with_ai()
                match_data = analyze_payload_with_ai(user_text)

                if not match_data.get('limit_players'):
                    _reply_text(event.reply_token, "請問這場預計招收幾人呢？（例如：6人）")
                    return

                draft_event = db.create_draft_event(user_id, match_data)
                flex_contents = generate_flex_message(match_data, draft_event["id"])
                _reply_flex(event.reply_token, "請確認開團資訊", flex_contents)
            except Exception as e:
                print(f"AI/Create Event Error: {e}")
                _reply_text(event.reply_token, "開團格式解析失敗，請再試一次！")
            return

        # 一般預設回應
        _reply_text(event.reply_token, f"收到你的訊息：{user_text}")

    # ------------------ 按鈕處理區塊 ------------------
    @handler.add(PostbackEvent)
    def handle_postback(event):
        params = parse_qs(event.postback.data)
        action = params.get('action', [None])[0]
        event_id = params.get('event_id', [None])[0]
        user_id = _get_user_id(event)
        db = _get_db()

        if not user_id:
            _reply_text(event.reply_token, "請先加官方帳號好友，才能幫你處理報名資料唷。")
            return

        if action == 'confirm' and event_id:
            confirmed = db.confirm_event(event_id)
            if not confirmed:
                _reply_text(event.reply_token, "找不到這場球局，可能已經被刪除了。")
                return
            success_contents = generate_success_card(
                date=confirmed.get("date_text") or "未定",
                location=confirmed.get("location") or "未定",
                time=confirmed.get("time_text") or "未定",
                limit=str(confirmed.get("limit_players") or 0),
            )
            _reply_flex(event.reply_token, "🎉 開團成功！", success_contents)
            return

        if action == 'join_event' and event_id:
            try:
                result = db.create_registration(event_id, user_id)
            except ValueError as e:
                _reply_text(event.reply_token, str(e))
                return

            limit = result["limit"]
            position = result["position_number"]

            if result["already_registered"]:
                status_label = "正取" if result["status"] == "registered" else "候補"
                msg = f"你已經在名單裡囉！（{status_label}第 {position} 位）"
            elif result["status"] == "registered":
                msg = f"✅ 報名成功！\n目前順位：第 {position} 位\n場次人數：{position}/{limit}"
            else:
                msg = f"⚠️ 目前正式名額已滿！\n已為你安排候補順位：第 {position} 位"
            _reply_text(event.reply_token, msg)
            return

        _reply_text(event.reply_token, "這個按鈕的資料格式有點問題，請重新操作一次。")
