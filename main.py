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
import os, requests
from linebot.models import TextSendMessage

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text
    reply = f"受け取りました: {user_text}"

    if "天気" in user_text:
        url = f"http://api.openweathermap.org/data/2.5/weather?q=Tokyo&appid={WEATHER_API_KEY}&lang=ja&units=metric"
        res = requests.get(url).json()
        if "main" in res:
            temp = res["main"]["temp"]
            desc = res["weather"][0]["description"]
            reply = f"今日の東京の天気: {desc}, {temp}℃"
        else:
            reply = "天気情報が取れませんでした。"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
