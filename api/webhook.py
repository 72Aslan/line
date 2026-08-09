import os
import sys
import json
import psycopg2
from flask import Flask, request, abort

# 確保當前目錄與上層目錄都在 sys.path 中，防範 Vercel 路徑迷路
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
for d in [current_dir, parent_dir]:
    if d not in sys.path:
        sys.path.insert(0, d)

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest,
    TextMessage, FlexMessage, FlexContainer
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, PostbackEvent

# flexTemplates 很輕量，直接載入沒關係
try:
    from api.flexTemplates import generate_flex_message, generate_success_card, generate_join_card
except ModuleNotFoundError:
    from flexTemplates import generate_flex_message, generate_success_card, generate_join_card

# aiService 會載入 google-genai SDK，延後到真的需要 AI 解析時才 import
def _get_analyze_payload_with_ai():
    try:
        from api.aiService import analyze_payload_with_ai
    except ModuleNotFoundError:
        from aiService import analyze_payload_with_ai
    return analyze_payload_with_ai

app = Flask(__name__)

# 安全讀取環境變數 (包含 Supabase 的連線網址)
channel_secret = os.getenv('LINE_CHANNEL_SECRET', '')
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', '')
postgres_url = os.getenv('POSTGRES_URL', '')

configuration = Configuration(access_token=channel_access_token)
handler = WebhookHandler(channel_secret) if channel_secret else None

MAX_LIMIT = 6
EVENT_KEY = 'badminton_815'

# ------------------ Supabase 資料庫操作函數 ------------------
def get_db_connection():
    return psycopg2.connect(postgres_url)

def get_event_signup_count():
    """從 Supabase 讀取最新報名人數"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT current_count FROM events WHERE event_key = %s;", (EVENT_KEY,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row[0] if row else 0
    except Exception as e:
        print(f"Database Get Error: {e}")
        return 0

def increment_signup_count():
    """在 Supabase 將報名人數 +1 並回傳最新人數"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE events SET current_count = current_count + 1 WHERE event_key = %s RETURNING current_count;", (EVENT_KEY,))
        new_count = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return new_count
    except Exception as e:
        print(f"Database Increment Error: {e}")
        return get_event_signup_count() + 1

# ------------------ Webhook 核心 ------------------
@app.route("/", methods=['GET', 'POST'])
@app.route("/api/webhook", methods=['GET', 'POST'])
def webhook():
    # 1. 處理 GET 測試（瀏覽器或 LINE 健康檢查）
    if request.method == 'GET':
        return 'LINE Bot Server Ready!', 200

    # 2. 處理 POST 請求
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)

    # 若 handler 未順利初始化或為 Verify 測試
    if not handler:
        return 'OK', 200

    try:
        handler.handle(body, signature)
    except Exception as e:
        # 強制捕捉所有例外並回傳 200，確保 LINE Verify 絕對能通過
        print(f"Webhook Exception caught: {e}")
        return 'OK', 200

    return 'OK', 200

# ------------------ 訊息處理區塊 ------------------
if handler:
    @handler.add(MessageEvent, message=TextMessageContent)
    def handle_message(event):
        user_text = event.message.text.strip()

        # 查球局 / 複製連結 / 查看場次資訊 (文字觸發)
        if user_text in ["查球局", "複製活動連結", "查看場次資訊"]:
            # 即時從資料庫獲取最新人數，確保卡片數據不卡零
            latest_count = get_event_signup_count()
            
            join_contents = generate_join_card(
                date="8/15", location="中山", time="19:00-21:00",
                level="初中階", fee=250, current=latest_count, limit=MAX_LIMIT
            )
            flex_message = FlexMessage(
                alt_text="8/15 中山羽球團 報名中！",
                contents=FlexContainer.from_dict(join_contents)
            )
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(reply_token=event.reply_token, messages=[flex_message])
                )
            return

        # 自然語言開團
        elif user_text.startswith('開團'):
            try:
                analyze_payload_with_ai = _get_analyze_payload_with_ai()
                match_data = analyze_payload_with_ai(user_text)
                with ApiClient(configuration) as api_client:
                    messaging_api = MessagingApi(api_client)

                    if not match_data.get('limit_players'):
                        messaging_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text="請問這場預計招收幾人呢？（例如：6人）")]
                            )
                        )
                        return

                    flex_contents = generate_flex_message(match_data)
                    flex_message = FlexMessage(
                        alt_text="請確認開團資訊",
                        contents=FlexContainer.from_dict(flex_contents)
                    )
                    messaging_api.reply_message(
                        ReplyMessageRequest(reply_token=event.reply_token, messages=[flex_message])
                    )
            except Exception as e:
                print(f"AI Error: {e}")
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token, 
                            messages=[TextMessage(text="開團格式解析失敗，請再試一次！")]
                        )
                    )
            return

        # 一般預設回應
        else:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=f"收到你的訊息：{user_text}")]
                    )
                )

    # ------------------ 按鈕處理區塊 ------------------
    @handler.add(PostbackEvent)
    def handle_postback(event):
        postback_data = event.postback.data
        
        # 處理確認開團
        
        if postback_data.startswith('action=confirm'):
            # 撈取最新人數傳入卡片
            latest_count = get_event_signup_count()
            
            success_contents = generate_success_card(
                date="8/15", location="中山", time="19:00-21:00", current=latest_count, limit=str(MAX_LIMIT)
            )
            flex_message = FlexMessage(
                alt_text="🎉 開團成功！", contents=FlexContainer.from_dict(success_contents)
            )
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(reply_token=event.reply_token, messages=[flex_message])
                )

        # 處理點擊卡片中的 +1 我要報名 按鈕
        elif postback_data == 'action=join_event':
            current_count = get_event_signup_count()
            if current_count < MAX_LIMIT:
                new_count = increment_signup_count()
                msg = f"✅ 報名成功！\n目前順位：第 {new_count} 位\n場次人數：{new_count}/{MAX_LIMIT}"
            else:
                new_count = increment_signup_count()
                wait_rank = new_count - MAX_LIMIT
                msg = f"⚠️ 目前正式名額已滿！\n已為您安排候補順位：第 {wait_rank} 位"

            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=msg)])
                )
