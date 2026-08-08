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
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from api.aiService import analyze_payload_with_ai
from api.flexTemplates import generate_flex_message

app = Flask(__name__)

# 從環境變數讀取 LINE 金鑰
channel_secret = os.getenv('LINE_CHANNEL_SECRET')
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')

configuration = Configuration(access_token=channel_access_token)
handler = WebhookHandler(channel_secret)


@app.route("/api/webhook", list=["POST"])
def webhook():
    # 檢查 LINE 簽章，確保請求安全
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text = event.message.text

    # 觸發自然語言開團
    if user_text.startswith('開團'):
        try:
            # 1. 呼叫 AI 解析白話文
            match_data = analyze_payload_with_ai(user_text)

            with ApiClient(configuration) as api_client:
                messaging_api = MessagingApi(api_client)

                # 2. 檢查關鍵欄位是否齊全（以人數為例）
                if not match_data.get('limit_players'):
                    messaging_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="請問這場預計招收幾人呢？（例如：6人）")]
                        )
                    )
                    return

                # 3. 產生 Flex 預覽確認卡片
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
        # 一般訊息罐頭回應
        with ApiClient(configuration) as api_client:
            messaging_api = MessagingApi(api_client)
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"收到你的 Python 訊息：{user_text}")]
                )
            )


# 讓 Vercel 能識別 Flask App
def handler_entry(environ, start_response):
    return app(environ, start_response)


# This is a sample Python script.

# Press ⌃F5 to execute it or replace it with your code.
# Press Double ⇧ to search everywhere for classes, files, tool windows, actions, and settings.


def print_hi(name):
    # Use a breakpoint in the code line below to debug your script.
    print(f'Hi, {name}')  # Press F9 to toggle the breakpoint.


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    print_hi('PyCharm')

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
