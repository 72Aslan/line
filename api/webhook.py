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
from api.flexTemplates import generate_flex_message, generate_success_card, generate_join_card

# 從環境變數讀取 LINE 金鑰
channel_secret = os.getenv('LINE_CHANNEL_SECRET')
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')

configuration = Configuration(access_token=channel_access_token)
handler = WebhookHandler(channel_secret)

# ------------------ 防呆全局變數預設值 ------------------
# 注意：在 Serverless 容器重啟時這些值會重置，後續引進 Supabase 資料庫才能永久儲存
current_signup_count = 0
MAX_LIMIT = 6

def handler(request):
    global current_signup_count
    
    if request.method != 'POST':
        return {'statusCode': 200, 'body': 'LINE Bot Webhook Ready'}

    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    try:
        # 定義文字訊息處理器
        @handler.add(MessageEvent, message=TextMessageContent)
        def handle_message(event):
            global current_signup_count
            user_text = event.message.text

            # 只要包含這些關鍵字，就強制噴出報名卡片，並確保有預設值
            if user_text in ["查球局", "複製活動連結", "查看場次資訊"]:
                join_contents = generate_join_card(
                    date="8/15",
                    location="中山",
                    time="19:00-21:00",
                    level="初中階",
                    fee=250,
                    current=current_signup_count,
                    limit=MAX_LIMIT
                )
                flex_message = FlexMessage(
                    alt_text="8/15 中山羽球團 報名中！",
                    contents=FlexContainer.from_dict(join_contents)
                )
                with ApiClient(configuration) as api_client:
                    messaging_api = MessagingApi(api_client)
                    messaging_api.reply_message(
                        ReplyMessageRequest(reply_token=event.reply_token, messages=[flex_message])
                    )
                return

            # 自然語言開團
            elif user_text.startswith('開團'):
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

                        flex_card = generate_flex_message(match_data)
                        messaging_api.reply_message(
                            ReplyMessageRequest(reply_token=event.reply_token, messages=[flex_card])
                        )
                except Exception as e:
                    print(f"AI Error: {e}")
                    with ApiClient(configuration) as api_client:
                        messaging_api = MessagingApi(api_client)
                        messaging_api.reply_message(
                            ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="開團格式解析失敗，請再試一次！")])
                        )
            
            else:
                # 一般罐頭回應
                with ApiClient(configuration) as api_client:
                    messaging_api = MessagingApi(api_client)
                    messaging_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=f"收到你的訊息：{user_text}")]
                        )
                    )

        # 定義按鈕點擊處理器
        @handler.add(PostbackEvent)
        def handle_postback(event):
            global current_signup_count
            postback_data = event.postback.data

            # 處理確認開團
            if postback_data.startswith('action=confirm'):
                success_contents = generate_success_card(
                    date="8/15", location="中山", time="19:00-21:00", limit=str(MAX_LIMIT)
                )
                flex_message = FlexMessage(
                    alt_text="🎉 開團成功！", contents=FlexContainer.from_dict(success_contents)
                )
                with ApiClient(configuration) as api_client:
                    messaging_api = MessagingApi(api_client)
                    messaging_api.reply_message(
                        ReplyMessageRequest(reply_token=event.reply_token, messages=[flex_message])
                    )

            # 處理球友 +1 報名
            elif postback_data == 'action=join_event':
                if current_signup_count < MAX_LIMIT:
                    current_signup_count += 1
                    msg = f"✅ 報名成功！\n目前順位：第 {current_signup_count} 位\n場次人數：{current_signup_count}/{MAX_LIMIT}"
                else:
                    wait_rank = current_signup_count - MAX_LIMIT + 1
                    msg = f"⚠️ 目前正式名額已滿！\n已為您安排候補順位：第 {wait_rank} 位"

                with ApiClient(configuration) as api_client:
                    messaging_api = MessagingApi(api_client)
                    messaging_api.reply_message(
                        ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=msg)])
                    )

        # 執行解析
        handler.handle(body, signature)
        return {'statusCode': 200, 'headers': {'Content-Type': 'application/json'}, 'body': json.dumps({'status': 'success'})}

    except InvalidSignatureError:
        return {'statusCode': 400, 'body': 'Invalid Signature'}
    except Exception as e:
        print(f"Global Error: {e}")
        return {'statusCode': 500, 'body': 'Internal Server Error'}
