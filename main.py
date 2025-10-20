# main.py
import os
import random
import requests
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

# LINE SDK
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)

# ===== 環境変数 =====
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    # Render 起動時の分かりやすいエラー
    print("⚠️ LINE の環境変数が設定されていません")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(LINE_CHANNEL_SECRET)

app = FastAPI()

# ====== In-Memory ユーザ状態（簡易）======
# user_state[user_id] = {"answer": 1-4}
user_state: Dict[str, Dict[str, Any]] = {}

# ===== ヘルスチェック =====
@app.get("/health")
def health():
    return {"status": "ok"}

# ===== 天気（OpenWeatherMap）=====
def fetch_weather(city: str) -> str:
    if not OPENWEATHER_API_KEY:
        return "天気 APIキーが未設定です（OPENWEATHER_API_KEY）。"
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {"q": city, "appid": OPENWEATHER_API_KEY, "lang": "ja", "units": "metric"}
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        data = r.json()
        desc = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        return f"{city}の天気: {desc} / 気温: {temp:.1f}℃"
    except Exception as e:
        return f"天気取得に失敗しました: {e}"

# ===== クイックリプライ共通 =====
def qr_choices():
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="①", text="①")),
        QuickReplyButton(action=MessageAction(label="②", text="②")),
        QuickReplyButton(action=MessageAction(label="③", text="③")),
        QuickReplyButton(action=MessageAction(label="④", text="④")),
        QuickReplyButton(action=MessageAction(label="次の問題", text="次の問題")),
        QuickReplyButton(action=MessageAction(label="ヘルプ", text="ヘルプ")),
    ])

def qr_next():
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="次の問題", text="次の問題")),
        QuickReplyButton(action=MessageAction(label="天気 例", text="天気 名古屋")),
        QuickReplyButton(action=MessageAction(label="ヘルプ", text="ヘルプ")),
    ])

HELP_TEXT = (
    "使い方：\n"
    "・「問題」→ 乙4 四択を出題（全50問からランダム）\n"
    "・「①②③④」をタップ→ 正誤判定\n"
    "・「次の問題」→ 次のランダム問題\n"
    "・「◯◯の天気」または「天気 ◯◯」→ 天気表示（例：天気 名古屋）"
)

# ====== 乙4：50問 ======
# answer は 1～4（①～④）
questions = [
    {"question": "アセトンは第4類の何に分類されるか？", "choices": ["第1石油類", "アルコール類", "第2石油類", "特殊引火物"], "answer": 2},
    {"question": "ガソリンの引火点に最も近いのは？", "choices": ["−20℃", "0℃", "30℃", "100℃"], "answer": 1},
    {"question": "灯油は第4類の何に分類されるか？", "choices": ["第1石油類", "第2石油類", "第3石油類", "第4石油類"], "answer": 2},
    {"question": "軽油は第4類の何に分類されるか？", "choices": ["第1石油類", "第2石油類", "第3石油類", "特殊引火物"], "answer": 3},
    {"question": "重油は第4類の何に分類されるか？", "choices": ["第2石油類", "第3石油類", "第4石油類", "アルコール類"], "answer": 3},
    {"question": "エタノールの分類は？", "choices": ["第1石油類", "第2石油類", "アルコール類", "自動車用燃料"], "answer": 3},
    {"question": "メタノールの分類は？", "choices": ["第1石油類", "アルコール類", "第2石油類", "第3石油類"], "answer": 2},
    {"question": "第1石油類の貯蔵の特徴は？", "choices": ["水より軽く混ざらない", "引火点が低い", "引火点が高い", "水に溶ける"], "answer": 2},
    {"question": "指定数量の定義として正しいのは？", "choices": ["製造上の量", "取扱いの基準量", "法令で危険物とみなす基準量", "容器の容量"], "answer": 3},
    {"question": "灯油（第2石油類：石油類）の指定数量は？", "choices": ["100L", "200L", "1000L", "2000L"], "answer": 3},
    {"question": "ガソリン（第1石油類）の指定数量は？", "choices": ["100L", "200L", "400L", "1000L"], "answer": 1},
    {"question": "重油（第4石油類）の指定数量は？", "choices": ["1000L", "2000L", "3000L", "4000L"], "answer": 2},
    {"question": "第1石油類の貯蔵容器として望ましい材質は？", "choices": ["ガラス", "ポリエチレン薄肉", "金属容器", "紙容器"], "answer": 3},
    {"question": "アルコール類に該当するものはどれ？", "choices": ["酢酸エチル", "イソプロパノール", "トルエン", "軽油"], "answer": 2},
    {"question": "危険物の標識で赤地に黒文字の意味は？", "choices": ["引火性液体", "酸化性固体", "自然発火性物質", "可燃性固体"], "answer": 1},
    {"question": "静電気対策として誤りは？", "choices": ["接地をする", "注入速度を上げる", "導電性ホースを使う", "湿度を保つ"], "answer": 2},
    {"question": "危険物の保管で『冷暗所』が必要なのは？", "choices": ["ガソリン", "メタノール", "アセトン", "全て"], "answer": 4},
    {"question": "泡消火薬剤が最も有効なのは？", "choices": ["金属火災", "電気火災", "油火災", "可燃性固体火災"], "answer": 3},
    {"question": "水系消火が不適なものは？", "choices": ["紙火災", "木材火災", "油火災", "布火災"], "answer": 3},
    {"question": "ガソリンの主な危険性は？", "choices": ["腐食性", "酸化性", "引火性・爆発性", "毒性のみ"], "answer": 3},
    {"question": "危険物施設の『少量危険物』とは？", "choices": ["指定数量未満", "指定数量の2倍", "指定数量の10分の1未満", "制限なし"], "answer": 3},
    {"question": "第2石油類の代表例は？", "choices": ["灯油・ジェット燃料", "ガソリン", "重油", "ベンゼン"], "answer": 1},
    {"question": "貯蔵タンクの防油堤の目的は？", "choices": ["換気", "漏えい拡大防止", "冷却", "装飾"], "answer": 2},
    {"question": "可燃性蒸気が最も溜まりやすい場所は？", "choices": ["高所", "低所・ピット", "屋外上空", "乾燥地帯"], "answer": 2},
    {"question": "危険物の『混載禁止』の理由は？", "choices": ["重量超過", "反応・危険増大", "税制の問題", "臭気の問題のみ"], "answer": 2},
    {"question": "引火点とは？", "choices": ["自然に燃える温度", "炎を近づけると燃えだす最低温度", "沸点", "発火点"], "answer": 2},
    {"question": "発火点とは？", "choices": ["外部からの炎で燃える温度", "自然に燃え始める温度", "引火点と同じ", "凝固点"], "answer": 2},
    {"question": "第3石油類の代表例は？", "choices": ["ベンゼン", "軽油", "ギヤオイル・クレオソート油", "ガソリン"], "answer": 3},
    {"question": "指定数量以上の貯蔵で必要になるのは？", "choices": ["特になし", "市町村長への届出", "許可", "ラベルのみ"], "answer": 3},
    {"question": "危険物施設の定期点検主目的は？", "choices": ["見栄え向上", "事故防止", "生産性向上", "費用削減"], "answer": 2},
    {"question": "水溶性の第1石油類は？", "choices": ["ベンゼン", "トルエン", "アセトン", "灯油"], "answer": 3},
    {"question": "アルコール類に共通する消火方法として有効なのは？", "choices": ["粉末・泡（耐アルコール性）", "水のみ", "二酸化炭素のみ", "砂のみ"], "answer": 1},
    {"question": "危険物の容器表示で誤りは？", "choices": ["内容物名", "危険等級", "指定数量を記載", "注意事項"], "answer": 3},
    {"question": "屋内タンクの換気で重要なのは？", "choices": ["送風のみ", "給気・排気のバランス", "遮光のみ", "冷却のみ"], "answer": 2},
    {"question": "第4類全般の共通的な主危険は？", "choices": ["酸化性", "腐食性", "引火性", "圧縮性"], "answer": 3},
    {"question": "気化しやすい順に近いのは？（常温）", "choices": ["ガソリン＞灯油＞重油", "灯油＞ガソリン＞重油", "重油＞灯油＞ガソリン", "ほぼ同じ"], "answer": 1},
    {"question": "指定数量の倍数が増えると要求されるのは？", "choices": ["標識縮小", "緩和措置", "安全対策の強化", "関係なし"], "answer": 3},
    {"question": "メタノールの主な危険・有害性で注意すべきは？", "choices": ["強い腐食性", "吸入毒性・失明の恐れ", "放射性", "窒息性"], "answer": 2},
    {"question": "危険物帳簿で最低限必要なのは？", "choices": ["装飾", "数量・入出庫・品名等の記録", "気温記録のみ", "不要"], "answer": 2},
    {"question": "火気厳禁区域の管理で誤りは？", "choices": ["標識設置", "周知徹底", "加熱作業の許可制", "喫煙所を内部に設置"], "answer": 4},
    {"question": "油火災時の初期消火で不適切なのは？", "choices": ["水散布", "泡消火器", "粉末消火器", "蓋をする"], "answer": 1},
    {"question": "貯蔵庫の照明で望ましいのは？", "choices": ["防爆仕様", "白熱裸電球", "ろうそく", "携帯ストーブ"], "answer": 1},
    {"question": "危険物施設での携帯電話使用で注意すべきは？", "choices": ["基本的に全面許可", "着火源となる可能性", "安全向上のみ", "影響なし"], "answer": 2},
    {"question": "容器のアース（接地）の目的は？", "choices": ["美観", "静電気の放電・着火防止", "重量測定", "冷却"], "answer": 2},
    {"question": "引火点が最も高いのはどれ？", "choices": ["ガソリン", "灯油", "軽油", "重油"], "answer": 4},
    {"question": "危険物の運搬で必要なのは？", "choices": ["運転免許のみ", "積載量・表示・書類等の遵守", "制服", "助手2名"], "answer": 2},
    {"question": "アルコール類の指定数量は？", "choices": ["100L", "200L", "400L", "600L"], "answer": 3},
    {"question": "静電気が発生しやすい操作は？", "choices": ["静置", "急速注入や濾過", "冷却", "加温のみ"], "answer": 2},
    {"question": "蒸気比重が空気より重い可燃蒸気の挙動は？", "choices": ["上へ拡散", "その場で消える", "低所へ滞留・流動", "影響なし"], "answer": 3},
    {"question": "『危険等級Ⅱ』に該当するのは一般に？", "choices": ["第1石油類", "第2石油類など", "第3石油類", "第4石油類"], "answer": 2},
    {"question": "灯油のおおよその引火点は？", "choices": ["−20℃", "0〜−10℃", "約40℃前後", "約100℃"], "answer": 3},
    {"question": "危険物取扱者（乙4）が現場で担う役割は？", "choices": ["販売のみ", "安全管理・取扱い監督など", "会計のみ", "搬入のみ"], "answer": 2},
]

# ===== 出題 =====
def make_quiz() -> Dict[str, Any]:
    q = random.choice(questions)
    text = (
        f"Q: {q['question']}\n"
        f"① {q['choices'][0]}\n"
        f"② {q['choices'][1]}\n"
        f"③ {q['choices'][2]}\n"
        f"④ {q['choices'][3]}"
    )
    return {"text": text, "answer": q["answer"]}

def send_quiz(user_id: str, reply_token: str):
    quiz = make_quiz()
    # 答えを記録
    user_state[user_id] = {"answer": quiz["answer"]}
    line_bot_api.reply_message(
        reply_token,
        TextSendMessage(text=quiz["text"], quick_reply=qr_choices())
    )

def judge_answer(user_id: str, reply_token: str, ans_text: str):
    if user_id not in user_state or "answer" not in user_state[user_id]:
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text="先に「問題」と送ってください。", quick_reply=qr_next())
        )
        return
    correct = user_state[user_id]["answer"]
    # ①②③④ or 1/2/3/4 に対応
    mapping = {"①":1,"②":2,"③":3,"④":4,"1":1,"2":2,"3":3,"4":4}
    user_ans = mapping.get(ans_text.strip(), None)
    if user_ans is None:
        line_bot_api.reply_message(reply_token, TextSendMessage(text="①〜④で答えてください。", quick_reply=qr_choices()))
        return
    if user_ans == correct:
        msg = "⭘ 正解！"
    else:
        msg = f"✕ 不正解… 正解は {['①','②','③','④'][correct-1]} でした。"
    # 次の問題へ誘導
    line_bot_api.reply_message(
        reply_token,
        TextSendMessage(text=msg, quick_reply=qr_next())
    )
    # 一旦答えは消して次の問題要求へ
    user_state.pop(user_id, None)

# ===== LINE Webhook =====
@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    try:
        events = parser.parse(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if not isinstance(event, MessageEvent):
            continue
        if not isinstance(event.message, TextMessage):
            continue

        user_id = event.source.user_id
        text = event.message.text.strip()

        # --- 天気 ---
        if text.endswith("の天気"):
            city = text.replace("の天気", "").strip()
            reply = fetch_weather(city)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply, quick_reply=qr_next()))
            continue
        if text.startswith("天気 "):
            city = text.split(" ", 1)[1].strip() if " " in text else ""
            reply = fetch_weather(city or "名古屋")
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply, quick_reply=qr_next()))
            continue

        # --- クイズ ---
        if text in ("問題", "次の問題"):
            send_quiz(user_id, event.reply_token)
            continue
        if text in ("①","②","③","④","1","2","3","4"):
            judge_answer(user_id, event.reply_token, text)
            continue

        if text == "ヘルプ":
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=HELP_TEXT, quick_reply=qr_next()))
            continue

        # デフォルトの案内
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="「問題」「①〜④で回答」「次の問題」/「◯◯の天気」または「天気 ◯◯」で使えます。", quick_reply=qr_next())
        )

    return JSONResponse({"status": "ok"})
