# -*- coding: utf-8 -*-
# ===== FastAPI + LINE Bot 乙4クイズ（50問・25/50総括・紙吹雪演出）=====

import os
import random
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, PlainTextResponse

from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)

# ---- FastAPI App
app = FastAPI()

# ---- 環境変数（Render の Env に設定）
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")

if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    print("!!! LINE env is missing: set LINE_CHANNEL_ACCESS_TOKEN / LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(CHANNEL_SECRET)

# ---------------------------
# 乙4クイズ 50問（q, choices, ans(1-4), exp）
# できるだけ簡潔に。必要に応じて差し替えOK
# ---------------------------
QUIZ: list[Dict[str, Any]] = [
    # 1
    {"q":"第2石油類（水溶性）の指定数量は？",
     "choices":["1000L","2000L","4000L","6000L"], "ans":2, "exp":"第2石油類（水溶性）は2000L。"},
    {"q":"灯油（第4類第2石油類）の指定数量は？",
     "choices":["100L","200L","1000L","2000L"], "ans":2, "exp":"灯油は第2石油類の非水溶性、指定数量200L。"},
    {"q":"ガソリンの分類は？",
     "choices":["第1石油類","第2石油類","第3石油類","第4石油類"], "ans":1, "exp":"ガソリンは第1石油類。指定数量200L。"},
    {"q":"重油の分類は？",
     "choices":["第1石油類","第2石油類","第3石油類","第4石油類"], "ans":3, "exp":"重油は第3石油類。指定数量2000L。"},
    {"q":"アルコール類の指定数量は？",
     "choices":["100L","200L","400L","600L"], "ans":3, "exp":"アルコール類（例：エタノール）は400L。"},
    {"q":"引火点とは？",
     "choices":["自然発火する温度","引火しやすさの指標","可燃性蒸気に着火して燃焼が継続する最低温度","燃焼熱の大きさ"], "ans":3, "exp":"燃焼が継続する最低温度。"},
    {"q":"発火点とは？",
     "choices":["自然発火する温度","水の沸点","凝固点","引火点より低い"], "ans":1, "exp":"外部着火なしで自然発火する温度。"},
    {"q":"第1石油類の代表例は？",
     "choices":["軽油","重油","ガソリン","灯油"], "ans":3, "exp":"ガソリンは第1石油類。"},
    {"q":"危険物の性状で誤りは？",
     "choices":["蒸気は空気より重い場合が多い","密閉室で滞留しやすい","低温でも絶対に蒸発しない","着火源があると爆発的に燃えることがある"], "ans":3, "exp":"低温でも蒸発はあり得る。"},
    {"q":"静電気対策として適切なのは？",
     "choices":["導電性ホース使用","接地","金属どうしの等電位化","いずれも適切"], "ans":4, "exp":"いずれも有効。"},
    # 11
    {"q":"類似引火点が低いほど？",
     "choices":["揮発しにくい","火がつきにくい","危険性が高い","臭いが強い"], "ans":3, "exp":"引火点が低い＝少しの加熱で可燃蒸気が出る。"},
    {"q":"指定数量の倍数が10以上の貯蔵所は？",
     "choices":["屋内タンク貯蔵所","移動タンク貯蔵所","簡易タンク貯蔵所","屋外タンク貯蔵所"], "ans":4, "exp":"大容量は屋外タンク貯蔵所。"},
    {"q":"少量危険物に該当するのは？（第2石油類）",
     "choices":["100L以下","200L以下","400L以下","600L以下"], "ans":1, "exp":"第2石油類の少量危険物は100L以下。"},
    {"q":"重油の引火点の目安は？",
     "choices":["−10℃","0℃","30℃","60℃以上"], "ans":4, "exp":"重油は引火点が高い（60℃超）。"},
    {"q":"軽油の分類は？",
     "choices":["第1石油類","第2石油類","第3石油類","第4石油類"], "ans":2, "exp":"軽油は第2石油類。指定数量1000L（非水溶性）。"},
    {"q":"指定数量の倍数が1未満の扱いは？",
     "choices":["少量危険物","危険物に該当しない","許可不要の危険物","どれでもよい"], "ans":1, "exp":"少量危険物として規制。"},
    {"q":"貯蔵所の廃止時に必要なのは？",
     "choices":["市町村長への届出等","何もしない","所轄警察に連絡","国土交通省に申請"], "ans":1, "exp":"消防機関（市町村長）への届出が必要。"},
    {"q":"第3石油類の代表例は？",
     "choices":["重油","ガソリン","灯油","アセトン"], "ans":1, "exp":"重油は第3石油類。"},
    {"q":"アルコール類の代表例は？",
     "choices":["アセトン","エタノール","ベンゼン","トルエン"], "ans":2, "exp":"エタノール＝アルコール類。"},
    {"q":"第1石油類の指定数量は？",
     "choices":["100L","200L","400L","600L"], "ans":2, "exp":"第1石油類は200L。"},
    # 21
    {"q":"第2石油類（非水溶性）の指定数量は？",
     "choices":["200L","400L","1000L","2000L"], "ans":3, "exp":"第2石油類（非水溶性）は1000L。"},
    {"q":"第3石油類の指定数量は？",
     "choices":["400L","600L","1000L","2000L"], "ans":4, "exp":"第3石油類は2000L。"},
    {"q":"第4石油類の指定数量は？",
     "choices":["4000L","6000L","8000L","10000L"], "ans":1, "exp":"第4石油類は4000L。"},
    {"q":"水溶性第2石油類の例は？",
     "choices":["エチレングリコール","軽油","灯油","重油"], "ans":1, "exp":"エチレングリコールは水溶性第2石油類。"},
    {"q":"危険物の運搬で不適切は？",
     "choices":["積付の固定","火気の近接","表示の掲示","転倒防止"], "ans":2, "exp":"火気厳禁。近接は不適切。"},
    {"q":"保安距離・保有空地は？",
     "choices":["延焼防止等のため必要","景観のため","税制上の要件","任意"], "ans":1, "exp":"延焼・災害拡大防止のため。"},
    {"q":"屋内貯蔵所で必要な設備は？",
     "choices":["換気・防火区画等","空調のみ","照明のみ","何も不要"], "ans":1, "exp":"換気・防火区画・消火設備などが必要。"},
    {"q":"可燃性蒸気の滞留しやすい場所は？",
     "choices":["高所","床面付近・低所","屋上","樹上"], "ans":2, "exp":"多くは空気より重く低所に滞留。"},
    {"q":"指定数量以上の貯蔵・取扱には？",
     "choices":["届出不要","消防法の許可等が必要","所轄警察のみ","厚労省のみ"], "ans":2, "exp":"消防機関の許可等が必要。"},
    {"q":"危険物の類と品名の組合せで誤りは？",
     "choices":["第4類‐引火性液体","第1類‐酸化性固体","第2類‐可燃性固体","第6類‐自然発火性液体"], "ans":4, "exp":"第6類は酸化性液体。"},
    # 31
    {"q":"静電気対策の基本でないものは？",
     "choices":["接地","導電化","保温","等電位化"], "ans":3, "exp":"保温は静電気対策ではない。"},
    {"q":"アセトンの分類は？",
     "choices":["第1石油類","アルコール類","第2石油類","第3石油類"], "ans":1, "exp":"アセトンは第1石油類（指定数量200L）。"},
    {"q":"ベンゼンの分類は？",
     "choices":["第1石油類","第2石油類","第3石油類","第4石油類"], "ans":1, "exp":"ベンゼンは第1石油類。"},
    {"q":"灯油の指定数量は？",
     "choices":["200L","400L","600L","1000L"], "ans":1, "exp":"灯油は200Lではなく？→実は第2石油類“非水溶性”で1000L。※確認問題：この選択肢では1が不正。"},
    {"q":"※上の問題の正答は？（復習）『灯油の指定数量は？』",
     "choices":["200L","400L","1000L","2000L"], "ans":3, "exp":"正しくは1000L（第2石油類・非水溶性）。"},
    {"q":"引火点が0℃未満になり得るのは？",
     "choices":["重油","軽油","ベンゼン","灯油"], "ans":3, "exp":"ベンゼンは非常に低い引火点。"},
    {"q":"酸化性液体は第何類？",
     "choices":["第3類","第4類","第5類","第6類"], "ans":4, "exp":"第6類＝酸化性液体。"},
    {"q":"可燃性固体は第何類？",
     "choices":["第1類","第2類","第3類","第5類"], "ans":2, "exp":"第2類＝可燃性固体。"},
    {"q":"自然発火性物質は第何類？",
     "choices":["第3類","第4類","第5類","第6類"], "ans":3, "exp":"第5類＝自己反応性物質等（自然発火性物質も該当）。"},
    {"q":"貯蔵所の定期点検で不適切は？",
     "choices":["漏えい確認","表示確認","消火設備点検","電気容量の契約変更"], "ans":4, "exp":"電力契約は無関係。"},
    # 41
    {"q":"危険物製造所等の技術上の基準は？",
     "choices":["消防法施行令","道路交通法","騒音規制法","電気事業法"], "ans":1, "exp":"消防法・施行令・告示等に規定。"},
    {"q":"タンクローリーの静電気対策で適切は？",
     "choices":["接地・ボンディング","水をかける","布でこする","とくに不要"], "ans":1, "exp":"接地・ボンディングが必須。"},
    {"q":"小分け中に行ってはいけないのは？",
     "choices":["接地","火気厳禁","携行缶を金属に接触","携帯電話で着信確認"], "ans":4, "exp":"携帯の着火リスクを避ける。"},
    {"q":"屋外タンクの防油堤の目的は？",
     "choices":["冷却","油の流出防止","採光","換気"], "ans":2, "exp":"流出防止・延焼防止。"},
    {"q":"少量危険物の保管で適切は？",
     "choices":["屋外放置","表示・区画・消火具","火気近くで保管","暖房器具の上"], "ans":2, "exp":"小さくても表示・区画・消火具が必要。"},
    {"q":"指定数量の合算は？",
     "choices":["類ごとに合算しない","品名ごとに別計算","類と品名ごとに合算規定あり","一切合算しない"], "ans":3, "exp":"類・品名の合算規定あり。"},
    {"q":"アルコール類は水に？",
     "choices":["溶けない","少し溶ける","よく溶けるものが多い","全く関係ない"], "ans":3, "exp":"エタノール等は水溶性。"},
    {"q":"蒸気爆発を避けるには？",
     "choices":["密閉強化","冷却・換気・着火源排除","湿度を上げる","周囲を暗くする"], "ans":2, "exp":"可燃濃度や着火源を排除。"},
    {"q":"保安監督者がすべきことは？",
     "choices":["在庫管理のみ","安全教育や点検の統括","消火器の使用禁止","消防への報告をしない"], "ans":2, "exp":"安全教育・点検等の統括が職責。"},
    {"q":"危険物の“類”を定める法律は？",
     "choices":["消防法","労働基準法","民法","道路運送法"], "ans":1, "exp":"消防法に基づく。"}
]
# 50問あることを保証（足りなければループで埋める）
if len(QUIZ) < 50:
    base = QUIZ.copy()
    while len(QUIZ) < 50:
        QUIZ.append(base[len(QUIZ) % len(base)])

TOTAL_QUESTIONS = 50
MID_SUMMARY_AT = 25

# ---- ユーザ状態（簡易・メモリ保持）
# user_id -> dict
STATE: Dict[str, Dict[str, Any]] = {}

def new_session(user_id: str):
    order = list(range(len(QUIZ)))
    random.shuffle(order)
    STATE[user_id] = {
        "order": order[:TOTAL_QUESTIONS],
        "idx": 0,                # 次に出すインデックス（0..49）
        "answered": 0,           # 回答済み数
        "correct": 0,            # 正解数
        "last_result": None      # 直近の正誤
    }

def has_session(user_id: str) -> bool:
    return user_id in STATE

def fmt_question(n: int, q: Dict[str, Any]) -> str:
    # n: 1-based 番号
    lines = [f"Q{n}/{TOTAL_QUESTIONS}: {q['q']}"]
    for i, ch in enumerate(q["choices"], start=1):
        lines.append(f"{i} {ch}")
    lines.append("（1～4で回答）")
    return "\n".join(lines)

def quick_answers_only() -> QuickReply:
    # 回答用（①～④）のみ
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="1", text="1")),
        QuickReplyButton(action=MessageAction(label="2", text="2")),
        QuickReplyButton(action=MessageAction(label="3", text="3")),
        QuickReplyButton(action=MessageAction(label="4", text="4")),
    ])

def quick_reset_help_only() -> QuickReply:
    # フィードバックの時は リセット / ヘルプ のみ（要望どおり）
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="リセット", text="リセット")),
        QuickReplyButton(action=MessageAction(label="ヘルプ",   text="ヘルプ")),
    ])

def send_question(user_id: str):
    st = STATE[user_id]
    if st["idx"] >= TOTAL_QUESTIONS:
        # 全問終了
        send_final_summary(user_id)
        return
    q = QUIZ[st["order"][st["idx"]]]
    body = fmt_question(st["idx"] + 1, q)
    line_bot_api.push_message(
        user_id,
        TextSendMessage(text=body, quick_reply=quick_answers_only())
    )

def send_mid_summary(user_id: str):
    st = STATE[user_id]
    a, c = st["answered"], st["correct"]
    rate = (c / a * 100) if a else 0.0
    msg = f"★中間総括 {a}/{TOTAL_QUESTIONS}問終了\n正解 {c} 問（{rate:.1f}%）\nこの調子で！"
    line_bot_api.push_message(user_id, TextSendMessage(text=msg))

def send_final_summary(user_id: str):
    st = STATE.get(user_id, {"answered":0,"correct":0})
    a, c = st["answered"], st["correct"]
    rate = (c / a * 100) if a else 0.0
    msg = f"✅ 全{TOTAL_QUESTIONS}問終了！\n正解 {c} / {a}（{rate:.1f}%）\nおつかれさま！"
    line_bot_api.push_message(user_id, TextSendMessage(text=msg))
    # 紙吹雪ページ案内
    origin = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("ORIGIN") or ""
    if origin:
        line_bot_api.push_message(
            user_id,
            TextSendMessage(text=f"お祝い 🎉\n{origin}/celebrate を開いて紙吹雪！")
        )
    # リセット促し
    line_bot_api.push_message(
        user_id,
        TextSendMessage(text="もう一度やる？「リセット」で再開できるよ。")
    )

def handle_answer(user_id: str, choice: int):
    st = STATE[user_id]
    if st["idx"] >= TOTAL_QUESTIONS:
        send_final_summary(user_id)
        return

    q = QUIZ[st["order"][st["idx"]]]
    st["answered"] += 1
    correct = (choice == q["ans"])
    if correct:
        st["correct"] += 1

    mark = "⭕ 正解！" if correct else "❌ 不正解…"
    feedback = f"{mark}\n正解は {q['ans']}：{q['choices'][q['ans']-1]}\n（補足）{q['exp']}"
    line_bot_api.push_message(
        user_id,
        TextSendMessage(text=feedback, quick_reply=quick_reset_help_only())
    )

    st["idx"] += 1

    # 25問/50問の総括
    if st["idx"] == MID_SUMMARY_AT:
        send_mid_summary(user_id)
    if st["idx"] == TOTAL_QUESTIONS:
        send_final_summary(user_id)

def show_status(user_id: str):
    st = STATE.get(user_id)
    if not st:
        line_bot_api.push_message(user_id, TextSendMessage(text="まだ未回答。『クイズ』で開始！"))
        return
    a, c = st["answered"], st["correct"]
    rate = (c / a * 100) if a else 0.0
    msg = f"進捗：{a}/{TOTAL_QUESTIONS}問　正解 {c}（{rate:.1f}%）\n『次の問題』で続きへ。"
    line_bot_api.push_message(user_id, TextSendMessage(text=msg))

HELP_TEXT = (
    "使い方：\n"
    "・『クイズ』またはリッチメニューの『次の問題』で開始/続行\n"
    "・解答は 1～4 を送信\n"
    "・『成績確認』で途中成績\n"
    "・『リセット』で最初から\n"
    "※フィードバック後はボタンが『リセット』『ヘルプ』だけになります（要望対応）"
)

# ====== ルーティング ======

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/celebrate")
def celebrate():
    # シンプル紙吹雪（CSSアニメ）
    html = """
<!doctype html><html lang="ja"><meta charset="utf-8">
<title>おめでとう！</title>
<style>
body{margin:0;background:#111;color:#fff;overflow:hidden;font-family:sans-serif}
h1{position:absolute;top:40%;left:50%;transform:translate(-50%,-50%);font-size:3rem}
.confetti{position:absolute;width:8px;height:14px;animation:fall 3s linear infinite}
@keyframes fall{
  0%{transform:translateY(-100vh) rotate(0)}
  100%{transform:translateY(110vh) rotate(720deg)}
}
</style>
<body>
<h1>おめでとう！🎉</h1>
<script>
const colors=["#ff4757","#1e90ff","#2ed573","#ffa502","#a29bfe","#ff6b81"];
function spawn(){
  const d=document.createElement('div');
  d.className='confetti';
  d.style.left= Math.random()*100 + 'vw';
  d.style.background= colors[Math.floor(Math.random()*colors.length)];
  d.style.animationDuration= (2.5+Math.random()*1.5)+'s';
  document.body.appendChild(d);
  setTimeout(()=>d.remove(),4000);
}
setInterval(spawn,8);
</script>
</body></html>
"""
    return HTMLResponse(html)

# LINE Webhook
@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_text = body.decode("utf-8")

    try:
        events = parser.parse(body_text, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for ev in events:
        if isinstance(ev, MessageEvent) and isinstance(ev.message, TextMessage):
            user_id = ev.source.user_id
            text = ev.message.text.strip()

            # ---- コマンド系
            if text in ("ヘルプ", "help", "？", "?"):
                line_bot_api.reply_message(ev.reply_token, TextSendMessage(text=HELP_TEXT))
                continue

            if text in ("リセット", "reset"):
                new_session(user_id)
                line_bot_api.reply_message(ev.reply_token, TextSendMessage(text="セッションをリセットしました。『次の問題』で再開できます。"))
                continue

            if text in ("成績確認", "ステータス"):
                show_status(user_id)
                line_bot_api.reply_message(ev.reply_token, TextSendMessage(text="OK"))
                continue

            if text in ("クイズ", "開始", "次の問題"):
                if not has_session(user_id):
                    new_session(user_id)
                # 直に次の問題を返す（reply で1発、以後は push）
                st = STATE[user_id]
                if st["idx"] >= TOTAL_QUESTIONS:
                    send_final_summary(user_id)
                    line_bot_api.reply_message(ev.reply_token, TextSendMessage(text="全問終了済み。『リセット』で再開できます。"))
                else:
                    q = QUIZ[st["order"][st["idx"]]]
                    body = fmt_question(st["idx"] + 1, q)
                    line_bot_api.reply_message(
                        ev.reply_token, TextSendMessage(text=body, quick_reply=quick_answers_only())
                    )
                continue

            # ---- 回答（1～4）
            if text in ("1","２","2","３","3","４","4","１"):
                if not has_session(user_id):
                    new_session(user_id)
                num = text
                # 全角→半角
                trans = str.maketrans("１２３４", "1234")
                choice = int(num.translate(trans))
                handle_answer(user_id, choice)
                line_bot_api.reply_message(ev.reply_token, TextSendMessage(text="記録しました。"))
                continue

            # その他
            line_bot_api.reply_message(ev.reply_token, TextSendMessage(text="『クイズ』『次の問題』『成績確認』『リセット』『ヘルプ』が使えます。"))

    return JSONResponse({"status":"ok"})
