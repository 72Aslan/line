from api.webhook import app

# 這行是為了讓 Vercel 的預設偵測器直接拿到 app 變數
app = app
