import os
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from linebot import LineBotApi
from linebot.models import TextSendMessage

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "ok"}

def get_line_bot_api() -> LineBotApi:
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        # 起動は成功させ、呼ばれた時だけ分かりやすくエラー
        raise HTTPException(status_code=500, detail="LINE_CHANNEL_ACCESS_TOKEN is not set")
    return LineBotApi(token)

@app.post("/callback")
async def callback(request: Request):
    body = await request.json()
    text = body.get("message", "")
    # ここで初めて SDK を初期化（起動時クラッシュを防ぐ）
    line_bot_api = get_line_bot_api()
    try:
        # 例: 送信テキストのエコー（適宜あなたの処理に置換）
        reply_token = body.get("replyToken")
        if reply_token and text:
            line_bot_api.reply_message(reply_token, TextSendMessage(text=f"受け取りました: {text}"))
        return JSONResponse({"status": "ok"})
    except Exception as e:
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)
