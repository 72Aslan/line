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
from linebot.v3.webhooks import MessageEvent, TextMessageContent, PostbackEvent
from api.aiService import analyze_payload_with_ai
from api.flexTemplates import generate_flex_message

# 1. 從環境變數讀取 LINE 金鑰
channel_secret = os.getenv('LINE_CHANNEL_SECRET')
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')

configuration = Configuration(access_token=channel_access_token)
handler = WebhookHandler(channel_secret)

# 2. Vercel Python Serverless 的主要入口函數（只負責接收與轉發）
def handler(request):
    if request.method != 'POST':
        return {
            'statusCode': 200,
            'body': 'LINE Bot Webhook Ready'
        }

    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    try:
        # 呼叫最外層的處理器來解析事件
        handler.handle(body, signature)
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'status': 'success'})
        }
    except InvalidSignatureError:
        return {'statusCode': 400, 'body': 'Invalid Signature'}
    except Exception as e:
        print(f"Webhook Error: {e}")
        return {'statusCode': 500, 'body': 'Internal Server Error'}


# =====================================================================
# 3. 核心監聽器：移到最外層（全域），避免重複註冊導致機器人卡死
# =====================================================================

# 📩 監聽文字訊息事件
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text = event.message.text

    if user_text.startswith('開團'):
        try:
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
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[flex_message]
                    )
                )

        except Exception as e:
            print(f"AI Analysis Error: {e}")
            with ApiClient(configuration) as api_client:
                messaging_api = MessagingApi(api_client)
                messaging_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="開團格式解析失敗，請再試一次！")]
                    )
                )
    else:
        with ApiClient(configuration) as api_client:
            messaging_api = MessagingApi(api_client)
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"收到你的訊息：{user_text}")]
                )
            )


# 🔘 監聽按鈕點擊事件 (Postback)
@handler.add(PostbackEvent)
def handle_postback(event):
    postback_data = event.postback.data
    print(f"收到 Postback 資料: {postback_data}")

    if postback_data.startswith('action=confirm'):
        with ApiClient(configuration) as api_client:
            messaging_api = MessagingApi(api_client)
            
            # 回覆開團成功 [cite: 82, 83, 84, 85]
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TextMessage(text="🎉 開團成功！\n8/15 中山羽球團\n19:00-21:00\n目前報名：0/6\n\n快將此卡片分享至群組吧！")
                    ]
                )
            )
