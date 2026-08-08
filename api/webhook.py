import os
import json
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    FlexMessage,
    FlexContainer
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, PostbackEvent
from api.aiService import analyze_payload_with_ai
from api.flexTemplates import generate_flex_message, generate_success_card

# 建立 Flask 應用程式實例
app = Flask(__name__)

# 從環境變數讀取 LINE 金鑰
channel_secret = os.getenv('LINE_CHANNEL_SECRET')
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')

configuration = Configuration(access_token=channel_access_token)
handler = WebhookHandler(channel_secret)

@app.route("/", methods=['POST'])
@app.route("/api/webhook", methods=['POST'])
def webhook():
    # 取得 LINE 簽章與內文
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception as e:
        print(f"Webhook Error: {e}")
        return 'Internal Server Error', 500

    return 'OK'

# 1. 處理使用者傳送文字訊息 (例如：開團...)
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text = event.message.text

    if user_text.startswith('開團'):
        try:
            # AI 語意分析
            match_data = analyze_payload_with_ai(user_text)

            with ApiClient(configuration) as api_client:
                messaging_api = MessagingApi(api_client)

                # 欄位檢查
                if not match_data.get('limit_players'):
                    messaging_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="請問這場預計招收幾人呢？（例如：6人）")]
                        )
                    )
                    return

                # 產生預覽確認 Flex 卡片
                flex_contents = generate_flex_message(match_data)
                flex_message = FlexMessage(
                    alt_text="請確認開團資訊",
                    contents=FlexContainer.from_dict(flex_contents)
                )

                messaging_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[flex_message]
                    )
                )

        except Exception as e:
            print(f"Error: {e}")
            with ApiClient(configuration) as api_client:
                messaging_api = MessagingApi(api_client)
                messaging_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="開團格式解析失敗，請再試一次！")]
                    )
                )
    else:
        # 一般文字回應
        with ApiClient(configuration) as api_client:
            messaging_api = MessagingApi(api_client)
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"收到你的訊息：{user_text}")]
                )
            )

# 2. 處理按鈕點擊 Postback 事件 (例如：按下「確認開團」)
@handler.add(PostbackEvent)
def handle_postback(event):
    postback_data = event.postback.data
    print(f"收到 Postback 資料: {postback_data}")

    if postback_data.startswith('action=confirm'):
        # 產生規格書要求的「開團成功與分享」Flex 卡片
        success_contents = generate_success_card(
            date="8/15",
            location="中山",
            time="19:00-21:00",
            limit="6"
        )
        
        flex_message = FlexMessage(
            alt_text="🎉 開團成功！",
            contents=FlexContainer.from_dict(success_contents)
        )

        with ApiClient(configuration) as api_client:
            messaging_api = MessagingApi(api_client)
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[flex_message]
                )
            )
