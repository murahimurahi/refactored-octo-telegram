import os
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# LINE SDK（既存のトークンを使う前提）
from linebot import LineBotApi
from linebot.models import TextSendMessage

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "ok"}

def get_weather_text(q: str) -> str:
    """
    q: 「天気」だけなら既定都市、例:「天気 東京」「天気 名古屋」ならその都市
    """
    api_key = os.getenv("WEATHER_API_KEY")
    if not api_key:
        return "天気APIキーが未設定です（WEATHER_API_KEY）。"

    # 都市名抽出（「天気 XXX」形式）
    parts = q.strip().split()
    city = "Tokyo"
    if len(parts) >= 2:  # 「天気 東京」など
        city = parts[1]

    url = (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?q={city}&appid={api_key}&lang=ja&units=metric"
    )
    try:
        r = requests.get(url, timeout=8)
        data = r.json()
        if r.status_code != 200 or "weather" not in data:
            return f"{city} の天気を取得できませんでした。"

        desc = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        humi = data["main"]["humidity"]
        return f"{city}の天気: {desc} / 気温: {temp}℃ / 湿度: {humi}%"
    except Exception:
        return "天気の取得中にエラーが発生しました。"

@app.post("/callback")  # ← LINEのWebhookはこのURLのままでOK
async def callback(request: Request):
    body = await request.json()
    # ざっくり処理（署名検証なしの簡易版）
    events = body.get("events", [])
    for ev in events:
        if ev.get("type") == "message" and ev.get("message", {}).get("type") == "text":
            reply_token = ev["replyToken"]
            text = ev["message"]["text"].strip()

            if text.startswith("天気"):
                reply = get_weather_text(text)
            else:
                reply = f"受け取りました: {text}"

            try:
                line_bot_api.reply_message(reply_token, TextSendMessage(text=reply))
            except Exception:
                # 返信に失敗しても200で返す（LINEの再試行を避ける）
                pass

    return JSONResponse({"status": "ok"})
