# main.py
# 乙4クイズ 50問 / FastAPI + LINE Messaging API（line-bot-sdk v2系）
# 必要な環境変数: LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET
# Render の Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT

import os
import random
from typing import Dict, List

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage,
    TextSendMessage, QuickReply, QuickReplyButton, MessageAction,
    FlexSendMessage
)

app = FastAPI()

# ---- health/root ------------------------------------------------------------
@app.get("/")
def root():
    return {"status": "ok", "message": "LINE Quiz Bot running."}

@app.get("/health")
def health():
    return {"status": "ok"}

# ---- お祝いHTML（25/50） ---------------------------------------------------
@app.get("/celebrate25", response_class=HTMLResponse)
def celebrate25():
    return """<!DOCTYPE html><html lang='ja'><head>
<meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>25問クリア！</title>
<style>
  html,body{margin:0;height:100%;background:#FFF8E1;font-family:system-ui,-apple-system,"Noto Sans JP",sans-serif;overflow:hidden;color:#333}
  .wrap{position:fixed;inset:0;display:grid;place-items:center;text-align:center;padding:24px}
  h1{margin:0 0 8px;font-size:28px} p{margin:0 0 16px;opacity:.8}
  .btn{display:inline-block;padding:12px 20px;border-radius:10px;background:#2e7d32;color:#fff;text-decoration:none;font-weight:700}
  #c{position:fixed;inset:0;pointer-events:none}
</style></head><body>
<canvas id='c'></canvas>
<div class='wrap'><div>
  <h1>🎉 前半25問クリア！</h1>
  <p>いい調子！このまま後半もがんばろう。</p>
  <a class='btn' href='javascript:history.back()'>トークに戻る</a>
</div></div>
<script src='https://cdn.jsdelivr.net/npm/canvas-confetti@1.9.3/dist/confetti.browser.min.js'></script>
<script>
  const my = confetti.create(document.getElementById('c'), { resize:true, useWorker:true });
  function burst(){ my({particleCount:120, spread:70, startVelocity:45, origin:{y:0.6}}); }
  burst(); setTimeout(burst,500);
  const end = Date.now()+2200; (function frame(){ my({particleCount:5, startVelocity:18, spread:70, ticks:120, origin:{x:Math.random(), y:Math.random()*0.2}});
    if(Date.now()<end) requestAnimationFrame(frame); })();
</script></body></html>"""

@app.get("/celebrate50", response_class=HTMLResponse)
def celebrate50():
    return """<!DOCTYPE html><html lang='ja'><head>
<meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>50問クリア！</title>
<style>
  html,body{margin:0;height:100%;background:linear-gradient(180deg,#FFFDE7,#FFF3E0);font-family:system-ui,-apple-system,"Noto Sans JP",sans-serif;overflow:hidden;color:#2c1900}
  .wrap{position:fixed;inset:0;display:grid;place-items:center;text-align:center;padding:24px}
  h1{margin:0 0 8px;font-size:30px} p{margin:0 0 16px;opacity:.9}
  .btn{display:inline-block;padding:12px 20px;border-radius:10px;background:#f9a825;color:#3e2723;text-decoration:none;font-weight:800;border:2px solid #3e2723}
  #c{position:fixed;inset:0;pointer-events:none}
</style></head><body>
<canvas id='c'></canvas>
<div class='wrap'><div>
  <h1>🏆 全50問クリア！</h1>
  <p>おつかれさま！堂々のフィニッシュ！</p>
  <a class='btn' href='javascript:history.back()'>トークに戻る</a>
</div></div>
<script src='https://cdn.jsdelivr.net/npm/canvas-confetti@1.9.3/dist/confetti.browser.min.js'></script>
<script>
  const my = confetti.create(document.getElementById('c'), { resize:true, useWorker:true });
  function superBurst(){
    my({ particleCount:180, spread:75, startVelocity:55, origin:{y:0.6}});
    my({ particleCount:180, spread:75, startVelocity:55, origin:{y:0.3}});
  }
  superBurst(); setTimeout(superBurst,600); setTimeout(superBurst,1200);
  const end = Date.now()+3500; (function frame(){ my({ particleCount:7, startVelocity:22, spread:90, ticks:140, origin:{x:Math.random(), y:Math.random()*0.25}});
    if(Date.now()<end) requestAnimationFrame(frame); })();
</script></body></html>"""

# ---- LINE 認証情報 ----------------------------------------------------------
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")

if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    print("[WARN] LINE 環境変数が未設定です。Render に設定してください。")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)  # type: ignore
handler = WebhookHandler(CHANNEL_SECRET)         # type: ignore

# ---- 問題（50問） ----------------------------------------------------------
QUESTIONS: List[Dict] = [
    {"q":"第2石油類（水溶性）の指定数量は？","choices":["1000L","2000L","4000L","6000L"],"ans":2,"exp":"第2石油類(水溶性)は2,000L。"},
    {"q":"第1石油類（非水溶性）の指定数量は？","choices":["200L","400L","1000L","2000L"],"ans":2,"exp":"第1石油類(非水溶性)は400L。"},
    {"q":"第1石油類（水溶性）の指定数量は？","choices":["200L","400L","1000L","2000L"],"ans":1,"exp":"第1石油類(水溶性)は200L。"},
    {"q":"第3石油類（非水溶性）の指定数量は？","choices":["1000L","2000L","4000L","6000L"],"ans":3,"exp":"第3石油類(非水溶性)は4,000L。"},
    {"q":"第4石油類の指定数量は？","choices":["1000L","2000L","4000L","6000L"],"ans":4,"exp":"第4石油類は6,000L。"},
    {"q":"アルコール類（引火点70℃未満）の指定数量は？","choices":["1000L","2000L","4000L","6000L"],"ans":2,"exp":"アルコール類は2,000L。"},
    {"q":"灯油（第2石油類・非水溶性）の指定数量は？","choices":["1000L","2000L","4000L","6000L"],"ans":2,"exp":"灯油は第2石油類(非水溶性)で2,000L。"},
    {"q":"重油（第3石油類・非水溶性）の指定数量は？","choices":["2000L","4000L","6000L","8000L"],"ans":2,"exp":"重油は第3石油類で4,000L。"},
    {"q":"潤滑油（第4石油類）の指定数量は？","choices":["2000L","4000L","6000L","8000L"],"ans":3,"exp":"潤滑油は第4石油類で6,000L。"},
    {"q":"ガソリンは何類？","choices":["第1石油類","第2石油類","第3石油類","第4石油類"],"ans":1,"exp":"ガソリンは第1石油類。"},
    {"q":"軽油は何類？","choices":["第1石油類","第2石油類","第3石油類","第4石油類"],"ans":2,"exp":"軽油は第2石油類。"},
    {"q":"重油は何類？","choices":["第1石油類","第2石油類","第3石油類","第4石油類"],"ans":3,"exp":"重油は第3石油類。"},
    {"q":"引火点が最も低いのは？","choices":["第1石油類","第2石油類","第3石油類","第4石油類"],"ans":1,"exp":"第1石油類は引火点が低い。"},
    {"q":"指定数量の倍数が10以上は何に該当？","choices":["少量危険物","危険物施設","貯蔵取扱所","屋内タンク貯蔵所"],"ans":3,"exp":"指定数量合計倍数で区分。"},
    {"q":"危険物標識の『危』の色は？","choices":["赤地白字","黄地黒字","白地赤字","青地白字"],"ans":1,"exp":"赤地に白字『危』。"},
    {"q":"指定数量未満で届出が不要なものは？","choices":["50Lのガソリン","100Lのガソリン","300Lの灯油","500Lの重油"],"ans":4,"exp":"重油4,000Lが指定数量。"},
    {"q":"静電気による火災防止で不適切は？","choices":["接地","導電性床","加湿","乾燥空気送入"],"ans":4,"exp":"乾燥は静電気をためやすい。"},
    {"q":"容器詰替時に守るべき事項は？","choices":["換気","静電気対策","火気厳禁","すべて"],"ans":4,"exp":"全て必要。"},
    {"q":"保安距離・保有空地が関係するのは？","choices":["製造所等","一般住宅","倉庫業法倉庫","事務所"],"ans":1,"exp":"製造所等の許可施設。"},
    {"q":"漏えい時にまず行うべきは？","choices":["点火源の除去","掃き集め","水で流す","放置"],"ans":1,"exp":"まず点火源除去。"},
    # ここから補完（合計50問）
    {"q":"灯油の類別・性状で正しいのは？","choices":["第1石油類","第2石油類・非水溶性","第3石油類","第4石油類"],"ans":2,"exp":"灯油は第2石油類・非水溶性。"},
    {"q":"アルコール類は一般に水溶性？","choices":["はい","いいえ","一部のみ","不明"],"ans":1,"exp":"メタノール等は水溶性。"},
    {"q":"ガソリンの蒸気は空気より？","choices":["軽い","重い","同じ","状況による"],"ans":2,"exp":"低所に滞留しやすい。"},
    {"q":"貯蔵タンクのアースは何のため？","choices":["腐食防止","静電気対策","漏えい防止","美観"],"ans":2,"exp":"静電気対策が主目的。"},
    {"q":"指定数量超の取扱いは？","choices":["自由","届出","許可・認可","税金のみ"],"ans":3,"exp":"許可等が必要。"},
    {"q":"容器置場で適切なのは？","choices":["直射日光","転倒防止","ドレン閉塞","火気近接"],"ans":2,"exp":"転倒防止・通風等。"},
    {"q":"類別で引火点に依存して区分されるのは？","choices":["第1〜4石油類","第5類","第6類","すべて"],"ans":1,"exp":"石油類は引火点で区分。"},
    {"q":"水で不適切になりやすい消火は？","choices":["極性溶剤火災","油火災","電気火災","いずれも不適切"],"ans":2,"exp":"油火災は泡が基本。"},
    {"q":"消火器の設置で適切なのは？","choices":["物陰に隠す","取り出しやすい位置","鍵付き収納","高所吊下げ"],"ans":2,"exp":"見やすく取り出しやすく。"},
    {"q":"ラベル表示で必要なのは？","choices":["品名","類別・数量","注意事項","すべて"],"ans":4,"exp":"識別できる表示が必要。"},
    {"q":"指定数量の合算は？","choices":["同類のみ合算","異類は不可","係数で合算","任意"],"ans":3,"exp":"係数（指定数量）で合算。"},
    {"q":"アセトンは何に分類？","choices":["第1石油類","アルコール類","第2石油類","特殊引火物"],"ans":2,"exp":"アルコール類相当。"},
    {"q":"メタノールは？","choices":["第1石油類","アルコール類","第2石油類","第3石油類"],"ans":2,"exp":"メタノールはアルコール類。"},
    {"q":"少量危険物の保管で不要なのは？","choices":["換気","区画","帳簿","火気厳禁"],"ans":3,"exp":"帳簿は原則不要（自治体要確認）。"},
    {"q":"貯蔵場の通路幅は？","choices":["狭いほど良い","一定の幅を確保","不要","塞いでよい"],"ans":2,"exp":"避難・搬出のため通路確保。"},
    {"q":"泡消火薬剤が有効なのは？","choices":["油火災","電気火災","金属火災","ガス火災"],"ans":1,"exp":"油面を覆って遮断・冷却。"},
    {"q":"金属火災に適した消火器は？","choices":["水系","粉末特殊","二酸化炭素","泡"],"ans":2,"exp":"金属火災は特殊粉末。"},
    {"q":"二酸化炭素消火器の注意点は？","choices":["閉鎖空間で窒息","腐食性強い","泡が出る","導電性あり"],"ans":1,"exp":"窒息の危険に注意。"},
    {"q":"運搬で必要なのは？","choices":["容器表示","積載固定","禁煙・火気厳禁","すべて"],"ans":4,"exp":"すべて必要。"},
    {"q":"保安講習の目的は？","choices":["技能向上","最新法令理解","事故防止","すべて"],"ans":4,"exp":"事故防止のため総合的に学ぶ。"},
    {"q":"滞留蒸気を避ける設計は？","choices":["低所に溝","換気","すべて","不要"],"ans":3,"exp":"換気や形状で滞留防止。"},
    {"q":"点検記録は？","choices":["不要","簡易でよい","保存する","口頭でOK"],"ans":3,"exp":"点検結果は保存。"},
    {"q":"静電気対策の一つでないのは？","choices":["接地","湿度管理","絶縁靴のみ","導電性床"],"ans":3,"exp":"絶縁靴だけでは不十分。"},
    {"q":"倍数が1未満の施設は？","choices":["製造所等","少量危険物取扱所","屋外貯蔵所","タンク貯蔵所"],"ans":2,"exp":"少量危険物の範囲。"},
    {"q":"ドラム缶開栓時の注意は？","choices":["火気厳禁","静電気対策","保護具","すべて"],"ans":4,"exp":"基本すべて必須。"},
    {"q":"危険物の『類』は？","choices":["4類のみ","3類と4類","1〜6類","1〜5類"],"ans":3,"exp":"1〜6類。"},
    {"q":"第4類危険物とは？","choices":["引火性液体","酸化性固体","自然発火性物質","酸類"],"ans":1,"exp":"第4類=引火性液体。"},
    {"q":"引火点とは？","choices":["火を近づけると燃える最低温度","沸点","発火点","蒸気圧"],"ans":1,"exp":"可燃性蒸気が着火する最低温度。"},
    {"q":"発火点とは？","choices":["自然発火する温度","引火点より低い","水の沸点","凝固点"],"ans":1,"exp":"外部火源無しで自然発火。"},
    {"q":"水溶性溶剤で注意する消火剤は？","choices":["通常泡","耐アルコール泡","水のみ","粉末のみ"],"ans":2,"exp":"極性溶剤には耐アルコール泡。"},
    {"q":"タンクゲージの目的は？","choices":["温度測定","濃度測定","液面管理","圧力測定"],"ans":3,"exp":"液面(量)の管理。"},
    {"q":"火花が出る工具の使用は？","choices":["どこでもOK","危険物周辺は避ける","水濡れならOK","屋外ならOK"],"ans":2,"exp":"点火源となるため避ける。"},
    {"q":"ラベルが剥がれた場合は？","choices":["そのまま使用","中身で判断","速やかに再表示","廃棄"],"ans":3,"exp":"識別できる表示を維持。"},
    {"q":"濃硫酸の希釈は？","choices":["水→濃硫酸","濃硫酸→水","同じ","発熱しない"],"ans":2,"exp":"水に酸を加える（逆は危険）。"},
    {"q":"火災時の通報は？","choices":["社内のみ","消防へ通報","メモだけ","放送不要"],"ans":2,"exp":"消防通報は基本。"},
    {"q":"避難経路の掲示は？","choices":["任意","必須","点検時のみ","夜間のみ"],"ans":2,"exp":"避難表示は重要。"},
    {"q":"漏えいした油の処理材は？","choices":["砂・オイルフィルタ","紙","水","布のみ"],"ans":1,"exp":"吸着材で回収。"},
    {"q":"指定数量の解釈で誤りは？","choices":["倍数合算する","一種類だけ合算","係数で合算","総量で判定"],"ans":2,"exp":"異種類も係数で合算。"},
    {"q":"施設の帳簿で必要なのは？","choices":["入出庫量","日付","担当者","すべて"],"ans":4,"exp":"トレーサビリティ確保。"},
]
TOTAL = len(QUESTIONS)  # 50

# ---- セッション -------------------------------------------------------------
class Session:
    def __init__(self):
        order = list(range(TOTAL))
        random.shuffle(order)
        self.order = order
        self.i = 0
        self.correct = 0
        self.answered = 0
        self.finished = False

SESS: Dict[str, Session] = {}

def ensure_session(uid: str) -> Session:
    if uid not in SESS:
        SESS[uid] = Session()
    return SESS[uid]

def reset_session(uid: str) -> Session:
    SESS[uid] = Session()
    return SESS[uid]

def current_question(sess: Session) -> Dict:
    return QUESTIONS[sess.order[sess.i]]

# ---- UI部品（クイックリプライ）--------------------------------------------
def qr_for_question() -> QuickReply:
    # 出題時：①②③④＋リセット＋ヘルプ（※ステータスなし）
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="①", text="1")),
        QuickReplyButton(action=MessageAction(label="②", text="2")),
        QuickReplyButton(action=MessageAction(label="③", text="3")),
        QuickReplyButton(action=MessageAction(label="④", text="4")),
        QuickReplyButton(action=MessageAction(label="リセット", text="リセット")),
        QuickReplyButton(action=MessageAction(label="ヘルプ", text="ヘルプ")),
    ])

def qr_after_feedback() -> QuickReply:
    # 回答後：リセット＋ヘルプのみ
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="リセット", text="リセット")),
        QuickReplyButton(action=MessageAction(label="ヘルプ", text="ヘルプ")),
    ])

# ---- 表示テキスト -----------------------------------------------------------
def format_question(sess: Session) -> str:
    q = current_question(sess)
    n = sess.i + 1
    return "\n".join([
        f"Q{n}/{TOTAL}: {q['q']}",
        f"① {q['choices'][0]}",
        f"② {q['choices'][1]}",
        f"③ {q['choices'][2]}",
        f"④ {q['choices'][3]}",
        "（①〜④で回答）",
    ])

def feedback_text(q: Dict, select: int, ok: bool) -> str:
    mark = "⭕ 正解！" if ok else "❌ 不正解…"
    correct_label = f"{q['ans']}：{q['choices'][q['ans']-1]}"
    return f"{mark}\n正解は {correct_label}\n（補足）{q['exp']}"

def score_text(sess: Session) -> str:
    rate = (sess.correct / sess.answered * 100) if sess.answered else 0.0
    return "累積成績：{0}/{1}問 正解（{2:.1f}%）".format(sess.correct, sess.answered, rate)

HELP_TEXT = (
    "使い方：\n"
    "・リッチメニューの『次の問題』で出題\n"
    "・回答は ①〜④ のどれかをタップ（クイックリプライ）\n"
    "・『リセット』でやり直し\n"
    "・『成績確認』と送ると累計成績を表示"
)

# ---- Flexカード -------------------------------------------------------------
def flex25(url: str) -> FlexSendMessage:
    bubble = {
      "type":"bubble","size":"mega",
      "styles":{"body":{"backgroundColor":"#FFF8E1"}},
      "body":{"type":"box","layout":"vertical","spacing":"md","contents":[
        {"type":"text","text":"🎉 前半25問クリア！","weight":"bold","size":"xl","color":"#333"},
        {"type":"text","text":"お祝いページを開いてね","size":"sm","color":"#666","wrap":True}
      ]},
      "footer":{"type":"box","layout":"vertical","contents":[
        {"type":"button","style":"primary","action":{"type":"uri","label":"開く","uri":url}}
      ]}
    }
    return FlexSendMessage(alt_text="25問クリア！", contents=bubble)

def flex50(url: str) -> FlexSendMessage:
    bubble = {
      "type":"bubble","size":"mega",
      "styles":{"body":{"backgroundColor":"#FFF3E0"}},
      "body":{"type":"box","layout":"vertical","spacing":"md","contents":[
        {"type":"text","text":"🏆 全50問クリア！","weight":"bold","size":"xl","color":"#3e2723"},
        {"type":"text","text":"おつかれさま！最終お祝いページへ","size":"sm","color":"#5d4037","wrap":True}
      ]},
      "footer":{"type":"box","layout":"vertical","contents":[
        {"type":"button","style":"primary","action":{"type":"uri","label":"開く","uri":url}}
      ]}
    }
    return FlexSendMessage(alt_text="50問クリア！", contents=bubble)

# ---- Webhook ---------------------------------------------------------------
class CallbackBody(BaseModel):
    events: list = []

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get('X-Line-Signature', '')
    body = await request.body()
    try:
        handler.handle(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    return "OK"

# ---- イベントハンドラ -------------------------------------------------------
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event: MessageEvent):
    uid = event.source.user_id
    text = (event.message.text or "").strip()

    # 開始・リセット
    if text in ["スタート", "開始", "クイズ", "クイズ開始"]:
        reset_session(uid)
        msg = "セッションを開始しました。50問ランダム出題します。\nリッチメニューの『次の問題』を押してください。"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        return

    if text == "リセット":
        reset_session(uid)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="セッションをリセットしました。\n『次の問題』で再開できます。")
        )
        return

    # 成績確認（ステータスボタンは出さないが、テキスト受理）
    if text in ["成績確認", "成績", "ステータス"]:
        sess = ensure_session(uid)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=score_text(sess), quick_reply=qr_after_feedback())
        )
        return

    # ヘルプ
    if text in ["ヘルプ", "help", "使い方"]:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=HELP_TEXT))
        return

    # 次の問題（リッチメニュー推奨／テキストでも可）
    if text in ["次の問題", "次", "next"]:
        sess = ensure_session(uid)
        if sess.finished:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="全50問終了済みです。『リセット』で再挑戦できます。", quick_reply=qr_after_feedback())
            )
            return
        qtxt = format_question(sess)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=qtxt, quick_reply=qr_for_question())
        )
        return

    # 回答（①〜④）
    sel = _choice_to_int(text)
    if sel:
        sess = ensure_session(uid)
        if sess.finished:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="全50問終了しました。『リセット』で再挑戦できます。", quick_reply=qr_after_feedback())
            )
            return

        q = current_question(sess)
        ok = (sel == q["ans"])
        sess.answered += 1
        if ok:
            sess.correct += 1

        fb = feedback_text(q, sel, ok)

        # 25問／50問で演出＋総括
        if sess.answered == 25:
            extra = "\n\n" + score_text(sess) + "\n（前半25問の中間総括）"
            line_bot_api.reply_message(
                event.reply_token,
                [
                    TextSendMessage(text=fb + extra, quick_reply=qr_after_feedback()),
                    flex25("https://{}/celebrate25".format(os.getenv("RENDER_EXTERNAL_HOSTNAME","example.onrender.com")))
                ]
            )
        elif sess.answered == TOTAL:
            extra = "\n\n" + score_text(sess) + "\n（最終総括：全50問）"
            sess.finished = True
            line_bot_api.reply_message(
                event.reply_token,
                [
                    TextSendMessage(text=fb + extra, quick_reply=qr_after_feedback()),
                    flex50("https://{}/celebrate50".format(os.getenv("RENDER_EXTERNAL_HOSTNAME","example.onrender.com")))
                ]
            )
        else:
            # 通常のフィードバックのみ
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=fb, quick_reply=qr_after_feedback())
            )

        # 次の問題へ（最終以外）
        if not sess.finished and sess.i < TOTAL - 1:
            sess.i += 1
        return

    # その他：ガイド or 現在問題を再掲
    sess = ensure_session(uid)
    if sess.finished:
        tip = "全50問終了しました。『リセット』で再挑戦できます。"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=tip, quick_reply=qr_after_feedback()))
    else:
        qtxt = format_question(sess)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=qtxt, quick_reply=qr_for_question())
        )

# ---- 入力の ①〜④ / 1〜4 判定 ----------------------------------------------
def _choice_to_int(t: str) -> int:
    t = t.strip()
    mapping = {
        "1":1,"１":1,"①":1,
        "2":2,"２":2,"②":2,
        "3":3,"３":3,"③":3,
        "4":4,"４":4,"④":4,
    }
    return mapping.get(t, 0)

# ---- ローカル実行（Renderでは未使用） --------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT","8000")))
