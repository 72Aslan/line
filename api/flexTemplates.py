def generate_flex_message(data):
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "📋 請確認開團資訊", "weight": "bold", "size": "lg"},
                {"type": "separator", "margin": "md"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "md",
                    "spacing": "sm",
                    "contents": [
                        {"type": "box", "layout": "horizontal", "contents": [{"type": "text", "text": "日期", "color": "#888888"}, {"type": "text", "text": data.get("date", "未設定"), "align": "end"}]},
                        {"type": "box", "layout": "horizontal", "contents": [{"type": "text", "text": "時間", "color": "#888888"}, {"type": "text", "text": data.get("time", "未設定"), "align": "end"}]},
                        {"type": "box", "layout": "horizontal", "contents": [{"type": "text", "text": "地點", "color": "#888888"}, {"type": "text", "text": data.get("location", "未設定"), "align": "end"}]},
                        {"type": "box", "layout": "horizontal", "contents": [{"type": "text", "text": "程度", "color": "#888888"}, {"type": "text", "text": data.get("level", "不限"), "align": "end"}]},
                        {"type": "box", "layout": "horizontal", "contents": [{"type": "text", "text": "人數", "color": "#888888"}, {"type": "text", "text": f"{data.get('limit_players', 0)}人", "align": "end"}]},
                        {"type": "box", "layout": "horizontal", "contents": [{"type": "text", "text": "費用", "color": "#888888"}, {"type": "text", "text": f"{data.get('fee', 0)}元", "align": "end"}]},
                        {"type": "box", "layout": "horizontal", "contents": [{"type": "text", "text": "用球", "color": "#888888"}, {"type": "text", "text": data.get("shuttlecock", "未設定"), "align": "end"}]}
                    ]
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#1DB954",
                    "action": {"type": "postback", "label": "確認開團", "data": "action=confirm"}
                },
                {
                    "type": "button",
                    "style": "secondary",
                    "action": {"type": "message", "label": "修改內容", "text": "重新開團"}
                }
            ]
        }
    }