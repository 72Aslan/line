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
from api.flexTemplates import generate_flex_message, generate_success_card, generate_join_card

# 建立 Flask 應用程式實例
app = Flask(__name__)

# 從環境變數讀取 LINE 金鑰
channel_secret = os.getenv('LINE_CHANNEL_SECRET')
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')

configuration = Configuration(access_token=channel_access_token)
handler = WebhookHandler(channel_secret)

# ------------------ 防呆全局變數 ------------------
current_signup_count = 0
MAX_LIMIT = 6

@app.route("/", methods=['POST'])
@app.route("/api/webhook", methods=['POST'])
def webhook():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception as e:
        print(f"Webhook Handler Error: {e}")
        return 'OK', 200 # 回傳 200 避免 LINE 持續重發造成卡死

    return 'OK'

# ------------------ 處理文字訊息 ------------------
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    global current_signup_count
    user_text = event.message.text.strip()

    # 1. 觸發報名卡片
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

    # 2. 自然語言開團
    # 2. 自然語言開團
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

                # ------ 修正這裡：確保只傳入字典資料，並正確轉成 FlexMessage ------
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
                messaging_api = MessagingApi(api_client)
                messaging_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token, 
                        messages=[TextMessage(text="開團格式解析失敗，請再試一次！")]
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
                    ReplyMessageRequest(
                        reply_token=event.reply_token, 
                        messages=[TextMessage(text="開團格式解析失敗，請再試一次！")]
                    )
                )
        return
        
    # 3. 其他一般罐頭回應
    else:
        with ApiClient(configuration) as api_client:
            messaging_api = MessagingApi(api_client)
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"收到你的訊息：{user_text}")]
                )
            )

# ------------------ 處理按鈕事件 ------------------
@handler.add(PostbackEvent)
def handle_postback(event):
    global current_signup_count
    postback_data = event.postback.data

    # 確認開團
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

    # 球友 +1 報名
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
