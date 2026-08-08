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


def generate_success_card(date, location, time, limit):
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "🎉 開團成功", "weight": "bold", "size": "xl", "color": "#1DB954"},
                {"type": "text", "text": f"{date} {location}羽球團", "weight": "bold", "size": "md", "margin": "md"},
                {"type": "text", "text": time, "size": "sm", "color": "#666666"},
                {"type": "separator", "margin": "lg"},
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "lg",
                    "contents": [
                        {"type": "text", "text": "目前報名", "color": "#888888"},
                        {"type": "text", "text": f"0/{limit} 人", "align": "end", "weight": "bold"}
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
                    "color": "#00B900",
                    "action": {
                        "type": "uri",
                        "label": "分享球局",
                        "uri": "https://line.me"
                    }
                },
                {
                    "type": "button",
                    "style": "secondary",
                    "action": {
                        "type": "message",
                        "label": "管理場次",
                        "text": "管理場次"
                    }
                },
                {
                    "type": "button",
                    "style": "link",
                    "action": {
                        "type": "message",
                        "label": "複製活動連結",
                        "text": "複製活動連結"
                    }
                }
            ]
        }
    }
    def generate_join_card(date, location, time, level, fee, current, limit):
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": f"{date} {location}羽球團", "weight": "bold", "size": "xl"},
                {"type": "separator", "margin": "md"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "md",
                    "spacing": "sm",
                    "contents": [
                        {"type": "box", "layout": "horizontal", "contents": [{"type": "text", "text": "時間", "color": "#888888"}, {"type": "text", "text": time, "align": "end"}]},
                        {"type": "box", "layout": "horizontal", "contents": [{"type": "text", "text": "程度", "color": "#888888"}, {"type": "text", "text": level, "align": "end"}]},
                        {"type": "box", "layout": "horizontal", "contents": [{"type": "text", "text": "費用", "color": "#888888"}, {"type": "text", "text": f"{fee}元", "align": "end"}]},
                        {"type": "box", "layout": "horizontal", "contents": [{"type": "text", "text": "名額", "color": "#888888"}, {"type": "text", "text": f"{current}/{limit}，尚缺{limit - current}人", "align": "end", "color": "#1DB954", "weight": "bold"}]}
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
                    "action": {
                        "type": "postback",
                        "label": "+1我要報名",
                        "data": "action=join_event"
                    }
                },
                {
                    "type": "button",
                    "style": "secondary",
                    "action": {
                        "type": "message",
                        "label": "查看場次資訊",
                        "text": "查看場次資訊"
                    }
                }
            ]
        }
    }
