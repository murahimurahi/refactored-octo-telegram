import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# OpenWeatherMapのAPIキーを環境変数から読み込む
OPENWEATHER_KEY = os.environ.get("OPENWEATHER_KEY")

# 日本語→英語の都市マッピング
CITY_MAP = {
    "東京": "Tokyo,jp",
    "名古屋": "Nagoya,jp",
    "大阪": "Osaka,jp",
    "京都": "Kyoto,jp",
    "札幌": "Sapporo,jp",
    "福岡": "Fukuoka,jp"
}

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    text = data["events"][0]["message"]["text"]

    reply = handle_message(text)

    return jsonify({
        "reply": reply
    })

def handle_message(text):
    # 「〇〇の天気」と聞かれたらCITY_MAPから検索
    if "天気" in text:
        for jp, en in CITY_MAP.items():
            if jp in text:
                return get_weather(en, jp)
        # どの都市にもマッチしなかった場合は東京
        return get_weather("Tokyo,jp", "東京")
    else:
        return f"受け取りました: {text}"

def get_weather(city_en, city_jp):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city_en}&appid={OPENWEATHER_KEY}&units=metric&lang=ja"
    r = requests.get(url)
    data = r.json()

    weather = data["weather"][0]["description"]
    temp = data["main"]["temp"]
    humidity = data["main"]["humidity"]

    return f"{city_jp}の天気: {weather} / 気温: {temp}℃ / 湿度: {humidity}%"

if __name__ == "__main__":
    app.run(port=5000)
