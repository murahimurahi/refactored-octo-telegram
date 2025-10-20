# main.py
import os
import random
import requests
from fastapi import FastAPI, Request, HTTPException
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

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("LINE の環境変数が未設定です。")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

app = FastAPI()


# ====== ヘルスチェック ======
@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/health")
def health():
    return {"status": "ok"}


# ====== 資格：乙4 四択クイズ ======
# 回答待ちユーザー → 正解（1-4）
user_expected_answer: dict[str, int] = {}

questions = [
    {
        "question": "アセトンは第4類の何に分類されるか？",
        "choices": ["第1石油類", "アルコール類", "第2石油類", "特殊引火物"],
        "answer": 2
    },
    {
        "question": "灯油（第4類第2石油類）の指定数量は？",
        "choices": ["100L", "200L", "1000L", "2000L"],
        "answer": 3
    },
    {
        "question": "ガソリンの引火点は概ね何℃未満？",
        "choices": ["0℃", "−20℃", "−40℃", "−10℃"],
        "answer": 3
    },
    {
        "question": "アルコール類に該当するものはどれ？",
        "choices": ["メタノール", "トルエン", "軽油", "潤滑油"],
        "answer": 1
    },
    {
        "question": "指定数量以上の危険物を貯蔵する場合に必要な許可は？",
        "choices": ["消防長等の承認", "知事の認可", "市町村長の許可", "国の許可"],
        "answer": 3
    },
    # ここに好きなだけ問題を追加してOK（形式は同じ）
]

def make_quick_answers(choices: list[str]) -> QuickReply:
    # ①②③④ のラベルで押すだけ回答（送信テキストは "1"~"4"）
    items = []
    marks = ["①", "②", "③", "④"]
    for i, label in enumerate(choices[:4], start=1):
        items.append(
            QuickReplyButton(
                action=MessageAction(label=f"{marks[i-1]} {label}", text=str(i))
            )
        )
    return QuickReply(items=items)

def make_next_button() -> QuickReply:
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="次の問題", text="次の問題")),
        QuickReplyButton(action=MessageAction(label="ヘルプ", text="ヘルプ")),
    ])

def send_quiz(event):
    q = random.choice(questions)
    user_id = event.source.user_id
    user_expected_answer[user_id] = q["answer"]
    text = (
        f"Q: {q['question']}\n"
        f"① {q['choices'][0]}\n"
        f"② {q['choices'][1]}\n"
        f"③ {q['choices'][2]}\n"
        f"④ {q['choices'][3]}"
    )
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=text, quick_reply=make_quick_answers(q["choices"]))
    )

def normalize_choice(s: str) -> int | None:
    s = s.strip()
    mapping = {
        "1":"1","１":"1","①":"1","1️⃣":"1",
        "2":"2","２":"2","②":"2","2️⃣":"2",
        "3":"3","３":"3","③":"3","3️⃣":"3",
        "4":"4","４":"4","④":"4","4️⃣":"4",
    }
    if s in mapping: return int(mapping[s])
    return None

def handle_answer(event, user_input: str):
    user_id = event.source.user_id
    expected = user_expected_answer.get(user_id)
    chosen = normalize_choice(user_input)
    if expected is None or chosen is None:
        # まだ出題してない/判定できない
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="『問題』と送ると四択問題を出すよ。", quick_reply=make_next_button())
        )
        return

    if expected == chosen:
        msg = "⭕ 正解！"
    else:
        marks = ["①","②","③","④"]
        msg = f"❌ 不正解… 正解は {marks[expected-1]} だよ。"

    # 次の問題ボタンを添付
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=msg, quick_reply=make_next_button())
    )
    # 1問ごとに状態クリア（連打対策したければ残してもOK）
    user_expected_answer.pop(user_id, None)


# ====== 天気（OpenWeather） ======
def fetch_weather(city: str) -> str:
    if not OPENWEATHER_API_KEY:
        return "天気APIキーが未設定です（OPENWEATHER_API_KEY）。"
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": OPENWEATHER_API_KEY,
        "lang": "ja",
        "units": "metric",
    }
    try:
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        d = r.json()
        desc = d["weather"][0]["description"]
        temp = d["main"]["temp"]
        return f"{city}の天気: {desc} / 気温: {temp:.1f}℃"
    except Exception:
        return f"{city}の天気を取得できませんでした。"


def send_help(event):
    help_msg = (
        "使い方：\n"
        "・『問題』… 乙4 四択クイズを出題（クイックリプライで回答）\n"
        "・『次の問題』… 次のランダム問題\n"
        "・『1～4』… 押す/入力で回答\n"
        "・『◯◯の天気』… 例：『名古屋の天気』\n"
    )
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_msg))


# ====== LINE Webhook ======
@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_text = body.decode("utf-8")

    try:
        handler.handle(body_text, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    return JSONResponse({"status": "ok"})


@handler.add(MessageEvent, message=TextMessage)
def on_message(event: MessageEvent):
    text = event.message.text.strip()

    # クイズ系
    if text in ["問題", "クイズ", "次の問題"]:
        send_quiz(event)
        return

    # 回答（1～4 / 各種表記）を判定
    if normalize_choice(text) is not None:
        handle_answer(event, text)
        return

    # 天気：『◯◯の天気』 or 『天気 ◯◯』
    if text.endswith("の天気"):
        city = text.replace("の天気", "").strip()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=fetch_weather(city)))
        return
    if text.startswith("天気 "):
        city = text.split(" ", 1)[1].strip()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=fetch_weather(city)))
        return

    if text in ["ヘルプ", "使い方", "help"]:
        send_help(event)
        return

    # デフォルト応答（メニュー誘導）
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(
            text="『問題』『次の問題』『◯◯の天気』『ヘルプ』からどうぞ。",
            quick_reply=QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="問題", text="問題")),
                QuickReplyButton(action=MessageAction(label="名古屋の天気", text="名古屋の天気")),
                QuickReplyButton(action=MessageAction(label="ヘルプ", text="ヘルプ")),
            ])
        )
    )
