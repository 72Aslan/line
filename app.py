import sys
import os

# 確保 Vercel 能順利將根目錄與 api 目錄加入環境路徑
sys.path.append(os.path.dirname(__file__))

from api.webhook import app

# 讓 Vercel 能夠順利識別 WSGI 進入點
application = app
