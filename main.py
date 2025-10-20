import os
import random
import requests
from typing import Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)

# ====== 環境変数 ======
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

app = FastAPI()

# ====== ヘルスチェック ======
@app.get("/health")
async def health():
    return {"status": "ok"}

# ====== 乙4クイズ（ランダム4択） ======
# answer は 0〜3（①〜④）
QUIZ_BANK = [
    {
        "q": "ガソリン（第4類第1石油類）の指定数量は？",
        "choices": ["① 100L", "② 200L", "③ 400L", "④ 1000L"],
        "answer": 0
    },
    {
        "q": "灯油（第4類第2石油類）の指定数量は？",
        "choices": ["① 100L", "② 200L", "③ 1000L", "④ 2000L"],
        "answer": 2
    },
    {
        "q": "軽油（第4類第2石油類）の指定数量は？",
        "choices": ["① 200L", "② 400L", "③ 800L", "④ 1000L"],
        "answer": 3
    },
    {
        "q": "アセトン（第4類第1石油類）の指定数量は？",
        "choices": ["① 100L", "② 200L", "③ 400L", "④ 800L"],
        "answer": 0
    },
    {
        "q": "危険物の貯蔵・取扱いで誤っているものは？",
        "choices": ["① 指定数量以上は許可が必要", "② 指定数量未満なら全て規制なし",
                    "③ 指定数量の倍数で“倍数”と表す", "④ 少量でも安全対策が必要"],
        "answer": 1
    },
]

# ユーザーごとの出題保持（簡易・揮発）
USER_STATE: Dict[str, Dict] = {}

LABELS = ["①", "②", "③", "④"]

def pick_question(user_id: str) -> Dict:
    q = random.choice(QUIZ_BANK)
    USER_STATE[user_id] = q
    return q

def quick_reply_for_choices() -> QuickReply:
    # ボタンを ①〜④ で返す（押すと “①/②/③/④” がそのままテキストになる）
    items = [QuickReplyButton(action=MessageAction(label=lab, text=lab)) for lab in LABELS]
    return QuickReply(items=items)

# ====== お天気（既存の簡易版） ======
def fetch_weather(city: str) -> str:
    if not OPENWEATHER_API_KEY:
        return "天気APIキーが未設定です（OPENWEATHER_API_KEY）。"
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "ja"}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        desc = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        return f"{city}の天気: {desc} / 気温: {temp:.1f}℃"
    except Exception:
        return f"{city}の天気が取得できませんでした。都市名を変えて試してみてください。"

# ====== LINE コールバック ======
@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    try:
        handler.handle(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        return JSONResponse(status_code=400, content={"message": "Invalid signature"})
    return JSONResponse(status_code=200, content={"message": "OK"})

@handler.add(MessageEvent, message=TextMessage)
def on_message(event: MessageEvent):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # ---- クイズの起動ワード ----
    if text in ["問題", "クイズ", "次", "次の問題"]:
        q = pick_question(user_id)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=q["q"] + "\n" + "\n".join(q["choices"]),
                            quick_reply=quick_reply_for_choices())
        )
        return

    # ---- 回答（①②③④）----
    if text in LABELS and user_id in USER_STATE:
        q = USER_STATE[user_id]
        selected_index = LABELS.index(text)
        correct_index = q["answer"]
        if selected_index == correct_index:
            result = "⭕ 正解！"
        else:
            result = f"❌ 不正解。正解は {LABELS[correct_index]}（{q['choices'][correct_index]}）です。"
        # 次の問題ボタン
        next_btn = QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="次の問題", text="次の問題"))
        ])
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=result, quick_reply=next_btn)
        )
        return

    # ---- 天気：『◯◯の天気』/『天気 ◯◯』----
    if text.endswith("の天気"):
        city = text.replace("の天気", "").strip()
        reply = fetch_weather(city)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return
    if text.startswith("天気 "):
        city = text.split(" ", 1)[1].strip()
        reply = fetch_weather(city)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # ---- ヘルプ ----
    help_msg = (
        "使い方:\n"
        "・「問題」/「クイズ」→ 乙4の4択問題を出題\n"
        "・「①/②/③/④」→ 回答ボタン\n"
        "・「次の問題」→ さらに出題\n"
        "・「名古屋の天気」/「天気 東京」→ 天気表示"
    )
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_msg))
