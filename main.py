import os, requests, re
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
WEATHER_KEY = os.getenv("OPENWEATHER_API_KEY")

if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    raise RuntimeError("LINEの環境変数が足りません。")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(CHANNEL_SECRET)
app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "ok"}

# 日本の主要都市だけ簡易対応（必要なら増やす）
CITY_MAP = {
    "名古屋": "Nagoya",
    "東京": "Tokyo",
    "大阪": "Osaka",
    "札幌": "Sapporo",
    "福岡": "Fukuoka",
    "京都": "Kyoto",
    "横浜": "Yokohama",
    "仙台": "Sendai",
}

def resolve_city(text: str) -> str:
    # 「○○の天気」「○○ 天気」などから都市名を抜く
    m = re.search(r"(.+?)\s*の?\s*天気", text)
    if m:
        jp = m.group(1).strip()
        if jp in CITY_MAP:
            return CITY_MAP[jp]
        # そのまま英語都市名と仮定
        return jp
    # 単に「天気」だけなら名古屋をデフォルト
    return CITY_MAP["名古屋"]

def get_weather(city_en: str) -> str:
    if not WEATHER_KEY:
        return "天気APIキーが未設定です（OPENWEATHER_API_KEY）。"
    url = (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?q={city_en},JP&appid={WEATHER_KEY}&lang=ja&units=metric"
    )
    try:
        r = requests.get(url, timeout=8)
        if r.status_code == 200:
            data = r.json()
            desc = data["weather"][0]["description"]
            temp = round(data["main"]["temp"], 1)
            name = data.get("name", city_en)
            return f"{name}の天気: {desc} / 気温: {temp}℃"
        else:
            return "天気情報を取得できませんでした。"
    except requests.RequestException:
        return "天気APIへの接続に失敗しました。"

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("x-line-signature")
    body = await request.body()
    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature")

    try:
        events = parser.parse(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=401, detail="Invalid signature")

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessage):
            text = event.message.text.strip()
            if "天気" in text:
                city = resolve_city(text)
                reply = get_weather(city)
            else:
                reply = "「○○の天気」と送ると天気を返します。例: 名古屋の天気"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

    return JSONResponse({"ok": True})
@app.get("/health")
def health():
    return {"status": "ok"}
