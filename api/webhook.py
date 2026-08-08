import os
import json
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

# 從環境變數讀取 LINE 金鑰
channel_secret = os.getenv('LINE_CHANNEL_SECRET')
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')

configuration = Configuration(access_token=channel_access_token)
handler = WebhookHandler(channel_secret)

# Vercel Python Serverless 的標準入口函數必須叫做 handler
def handler(request):
    # 檢查是否為 POST 請求
    if request.method != 'POST':
        return {
            'statusCode': 200,
            'body': 'LINE Bot Webhook Ready'
        }

    # 取得 LINE 的簽章與 Body
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    try:
        # 觸發 LINE 事件處理
        @handler.add(MessageEvent, message=TextMessageContent)
        def handle_message(event):
            user_text = event.message.text

            if user_text.startswith('開團'):
                try:
                    # 1. AI 語意分析
                    match_data = analyze_payload_with_ai(user_text)

                    with ApiClient(configuration) as api_client:
                        messaging_api = MessagingApi(api_client)

                        # 2. 欄位檢查
                        if not match_data.get('limit_players'):
                            messaging_api.reply_message(
                                ReplyMessageRequest(
                                    reply_token=event.reply_token,
                                    messages=[TextMessage(text="請問這場預計招收幾人呢？（例如：6人）")]
                                )
                            )
                            return

                        # 3. 產生 Flex Card 卡片
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
                # 一般訊息回應
                with ApiClient(configuration) as api_client:
                    messaging_api = MessagingApi(api_client)
                    messaging_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=f"收到你的訊息：{user_text}")]
                        )
                    )

        # 執行 LINE SDK 的解析
        handler.handle(body, signature)
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'status': 'success'})
        }

    except InvalidSignatureError:
        return {
            'statusCode': 400,
            'body': 'Invalid Signature'
        }
    except Exception as e:
        print(f"Webhook Error: {e}")
        return {
            'statusCode': 500,
            'body': 'Internal Server Error'
        }
