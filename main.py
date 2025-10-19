from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os

app = FastAPI()

# Renderの環境変数から読む
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/callback")
async def callback(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Line-Signature")

    try:
        handler.handle(body.decode("utf-8"), signature)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)

    return JSONResponse(content={"message": "ok"}, status_code=200)

# LINEからメッセージが来たら返信
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="受け取りました: " + event.message.text)
    )
