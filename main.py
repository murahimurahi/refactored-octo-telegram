
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
# 先頭の import の所に追加
import httpx

# --- ここから追記 ---
# 対応都市（必要なら増やせばOK）
CITY_DB = {
    "東京": ("Tokyo", 35.676, 139.650),
    "名古屋": ("Nagoya", 35.1815, 136.9066),
    "大阪": ("Osaka", 34.6937, 135.5023),
}

def pick_city(text: str):
    t = text.lower()
    for ja, (en, lat, lon) in CITY_DB.items():
        if ja in text or en.lower() in t:
            return ja, lat, lon
    return "東京", *CITY_DB["東京"][1:]  # デフォルト東京

async def handle_weather(text: str) -> str:
    # 「天気」が含まれなければ従来どおりエコー
    if "天気" not in text:
        return f"受け取りました: {text}"

    city_ja, lat, lon = pick_city(text)
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current_weather=true&timezone=Asia%2FTokyo"
    )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            r.raise_for_status()
            cw = r.json()["current_weather"]
        temp = cw.get("temperature")
        wind = cw.get("windspeed")
        return f"{city_ja}の天気: 気温 {temp}°C / 風速 {wind} m/s"
    except Exception:
        return f"{city_ja}の天気取得に失敗しました。少し待って再度お試しください。"
# --- ここまで追記 ---

# （LINEのテキスト受信処理の中）
# user_text = event.message.text.strip()
# これまでの「受け取りました: ...」を返す行を以下に差し替え
reply_text = await handle_weather(user_text)
line_bot_api.reply_message(event.reply
