# main.py ー 乙4クイズ50問（LINE）/ クイックリプライ / SQLite成績 / 10問ごと途中成績 & 最終成績 / /health
import os, random, sqlite3
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)

# ===== 環境変数 =====
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(LINE_CHANNEL_SECRET)

app = FastAPI()

# ===== SQLite（成績保存）=====
conn = sqlite3.connect("results.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS results (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT,
  qid INTEGER,
  correct INTEGER,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
""")
conn.commit()

def save_result(user_id: str, qid: int, correct: bool):
    cur.execute("INSERT INTO results (user_id, qid, correct) VALUES (?, ?, ?)",
                (user_id, qid, 1 if correct else 0))
    conn.commit()

def get_stats(user_id: str):
    cur.execute("SELECT COUNT(*), SUM(correct) FROM results WHERE user_id=?", (user_id,))
    total, ok = cur.fetchone()
    total = total or 0
    ok = ok or 0
    rate = round((ok/total)*100, 1) if total else 0.0
    return total, ok, rate

# ===== クイックリプライ =====
def qr_choices(choices: list[str]):
    marks = ["①", "②", "③", "④"]
    items = []
    for i, ch in enumerate(choices):
        items.append(QuickReplyButton(action=MessageAction(label=f"{marks[i]} {ch}", text=str(i+1))))
    items.append(QuickReplyButton(action=MessageAction(label="次の問題", text="次の問題")))
    items.append(QuickReplyButton(action=MessageAction(label="成績確認", text="成績確認")))
    return QuickReply(items=items)

def qr_menu():
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="問題", text="問題")),
        QuickReplyButton(action=MessageAction(label="次の問題", text="次の問題")),
        QuickReplyButton(action=MessageAction(label="ステータス", text="ステータス")),
        QuickReplyButton(action=MessageAction(label="成績確認", text="成績確認")),
        QuickReplyButton(action=MessageAction(label="リセット", text="リセット")),
        QuickReplyButton(action=MessageAction(label="ヘルプ", text="ヘルプ")),
    ])

HELP_TEXT = (
    "📘 乙４クイズBot（全50問）\n"
    "・『問題』『次の問題』→ 出題\n"
    "・①〜④をタップ→ 採点\n"
    "・10問ごとに途中成績、50問目で最終成績を自動表示\n"
    "・『ステータス』→ 途中成績\n"
    "・『成績確認』→ これまでの累積正答率（DB）\n"
    "・『リセット』→ 50問セッションやり直し\n"
)

# ===== ユーザー状態（セッション管理）=====
# user_state[user_id] = { "qid": int|None, "answer": int|None, "count": int, "correct": int, "target": int }
user_state: Dict[str, Dict[str, Any]] = {}
DEFAULT_SESSION_LEN = 50

def get_or_init_state(user_id: str) -> Dict[str, Any]:
    st = user_state.get(user_id)
    if not st:
        st = {"qid": None, "answer": None, "count": 0, "correct": 0, "target": DEFAULT_SESSION_LEN}
        user_state[user_id] = st
    return st

def reset_session(user_id: str):
    user_state[user_id] = {"qid": None, "answer": None, "count": 0, "correct": 0, "target": DEFAULT_SESSION_LEN}

# ===== 乙4 過去問系50問（オリジナル表現）=====
# answer は 1〜4（①〜④）
Q = [
    # 分類・指定数量
    {"question":"第4類危険物の共通性質は？","choices":["引火性液体","酸化性固体","自然発火性","可燃性固体"],"answer":1},
    {"question":"ガソリンの分類・指定数量は？","choices":["第1石油類・非水溶性・200L","第1石油類・水溶性・400L","第2石油類・非水溶性・1000L","第3石油類・非水溶性・2000L"],"answer":1},
    {"question":"アセトンの指定数量は？（水溶性第1石油類）","choices":["200L","400L","1000L","50L"],"answer":2},
    {"question":"灯油の指定数量は？（第2石油類・非水溶）","choices":["200L","400L","1000L","2000L"],"answer":3},
    {"question":"軽油の指定数量は？（第3石油類・非水溶）","choices":["1000L","2000L","4000L","6000L"],"answer":2},
    {"question":"重油の分類・指定数量は？","choices":["第3石油類・2000L","第4石油類・6000L","第2石油類・1000L","第1石油類・200L"],"answer":2},
    {"question":"アルコール類（エタノール等）の指定数量は？","choices":["200L","400L","1000L","2000L"],"answer":2},
    {"question":"第2石油類（水溶性）の指定数量は？","choices":["1000L","2000L","4000L","6000L"],"answer":2},
    {"question":"第3石油類（水溶性）の指定数量は？","choices":["2000L","4000L","6000L","1000L"],"answer":2},
    {"question":"特殊引火物の指定数量は？","choices":["200L","400L","50L","6000L"],"answer":3},

    # 引火点・性状
    {"question":"第1石油類の引火点は？","choices":["21℃未満","21〜70℃未満","70〜200℃未満","200℃以上"],"answer":1},
    {"question":"第2石油類の引火点は概ね？","choices":["21℃未満","約21〜70℃未満","約70〜200℃未満","200℃以上"],"answer":2},
    {"question":"第3石油類の引火点は？","choices":["21℃未満","21〜70℃未満","70〜200℃未満","200℃以上"],"answer":3},
    {"question":"第4石油類の引火点は？","choices":["21℃未満","70〜200℃未満","200℃以上","0℃未満"],"answer":3},
    {"question":"ガソリン蒸気の挙動で正しいのは？","choices":["空気より軽く上昇","空気より重く低所に滞留","空気と同じで拡散","比重は関係ない"],"answer":2},
    {"question":"灯油の性質で正しいのは？","choices":["ガソリンより引火点が高い","水に混和しやすい","第1石油類に分類","蒸気は空気より軽い"],"answer":1},
    {"question":"メタノールの注意点は？","choices":["強い吸入毒性の懸念","静電気の心配は不要","水に混和しない","油火災用泡が効かない"],"answer":1},
    {"question":"可燃性蒸気は一般に…","choices":["高所にたまる","低所・ピットにたまる","どこにも滞留しない","必ず屋外に散逸する"],"answer":2},
    {"question":"ベンゼンの分類は？","choices":["第1石油類・非水溶性","第1石油類・水溶性","第2石油類・非水溶性","アルコール類"],"answer":1},
    {"question":"イソプロパノール（IPA）の分類は？","choices":["第1石油類","アルコール類","第2石油類","第3石油類"],"answer":2},

    # 消火・設備
    {"question":"油火災に最適な消火は？","choices":["大量放水","泡消火","砂は不可","二酸化炭素は常に不可"],"answer":2},
    {"question":"ガソリン火災に不適切なのは？","choices":["泡","粉末","大量の放水","二酸化炭素"],"answer":3},
    {"question":"静電気対策として適切なのは？","choices":["接地（アース）","注入は極端に速く","湿度は低いほど良い","非導電ホース使用"],"answer":1},
    {"question":"防油堤の目的は？","choices":["換気","漏えい拡大防止","冷却","装飾"],"answer":2},
    {"question":"屋内照明で望ましいのは？","choices":["防爆仕様","白熱裸電球","ろうそく","可搬ストーブ"],"answer":1},
    {"question":"容器表示で必要なのは？","choices":["内容物名・危険等級等","会社名のみ","容量のみ","製造年月日のみ"],"answer":1},
    {"question":"第4類共通の主危険は？","choices":["酸化性","腐食性","引火性","窒息性"],"answer":3},
    {"question":"指定数量以上で必要なのは？","choices":["特になし","許可","口頭連絡","写真保存"],"answer":2},
    {"question":"『少量危険物』の概念に近いのは？","choices":["指定数量の5分の1未満","指定数量の2倍","無制限","第1石油類のみ対象"],"answer":1},
    {"question":"危険物帳簿に必要なのは？","choices":["色・匂い","数量・品名・入出庫","写真のみ","不要"],"answer":2},

    # 運搬・取扱
    {"question":"運搬時に必要なのは？","choices":["積載量遵守・表示・書類等","制服","助手2名","音楽"],"answer":1},
    {"question":"タンク注入で不適切なのは？","choices":["注入速度を上げ続ける","アースを取る","導電性ホース使用","飛散防止"],"answer":1},
    {"question":"混載禁止の理由は？","choices":["重量超過","反応・危険増大","税制","臭気"],"answer":2},
    {"question":"換気で重要なのは？","choices":["給気のみ","排気のみ","給気・排気のバランス","換気不要"],"answer":3},
    {"question":"静電気が発生しやすい操作は？","choices":["静置","急速注入や濾過","冷却","加温のみ"],"answer":2},
    {"question":"容器接地（アース）の目的は？","choices":["美観","静電気放電","重量測定","冷却"],"answer":2},
    {"question":"携帯電話の注意点は？","choices":["常時安全","着火源になり得る","消火器の代用可","影響なし"],"answer":2},
    {"question":"漏えい時にまず優先するのは？","choices":["SNS報告","着火源除去・拡大防止","写真撮影","臭気対策"],"answer":2},
    {"question":"保安容器の目的は？","choices":["装飾","飛散・揮発抑制と安全注ぎ","重量増","保温"],"answer":2},
    {"question":"可燃蒸気の比重が空気より大きいと…","choices":["上昇散逸","低所へ流下・滞留","常に無害","気圧のみ依存"],"answer":2},

    # 物理化学
    {"question":"沸点が低いほど一般に…","choices":["揮発しにくい","揮発しやすい","引火しにくい","危険性は下がる"],"answer":2},
    {"question":"ガソリンは水に…","choices":["混和しやすい","ほとんど混和しない","完全溶解","必ず沈む"],"answer":2},
    {"question":"アルコール類は水に…","choices":["混和しにくい","ほとんど混和しない","混和しやすい","浮く"],"answer":3},
    {"question":"'引火点'の定義は？","choices":["自然発火温度","外火で燃え出す最低温度","沸点","凝固点"],"answer":2},
    {"question":"'発火点'の定義は？","choices":["外火なしで自然に燃える温度","外火で燃える温度","引火点と同じ","凝固点"],"answer":1},
    {"question":"可燃限界で正しいのは？","choices":["濃すぎても薄すぎても燃えない範囲がある","濃いほど必ず燃える","薄いほど必ず燃える","限界はない"],"answer":1},
    {"question":"蒸気雰囲気で爆発を起こしやすい条件は？","choices":["可燃限界内","可燃限界外（濃すぎ）","可燃限界外（薄すぎ）","常に同じ"],"answer":1},
    {"question":"静電気着火を抑える方法は？","choices":["乾燥させる","導電路と接地を設ける","保温する","攪拌を激しくする"],"answer":2},
    {"question":"水溶性第1石油類の例は？","choices":["アセトン","ベンゼン","トルエン","キシレン"],"answer":1},
    {"question":"第3石油類（水溶性）の例は？","choices":["クレオソート油","エチレングリコール","ギヤオイル","タービン油"],"answer":2},

    # 法令・管理
    {"question":"指定数量以上の貯蔵・取扱いで必要なのは？","choices":["許可","届出不要","口頭報告","自主判断"],"answer":1},
    {"question":"危険物施設の定期点検の主目的は？","choices":["見栄え向上","事故防止","生産性向上","費用削減"],"answer":2},
    {"question":"標識『火気厳禁』で不適切なのは？","choices":["標識設置","周知徹底","内部に喫煙所設置","加熱作業の許可制"],"answer":3},
    {"question":"屋内貯蔵所の換気で重要なのは？","choices":["給気のみ","排気のみ","給気・排気のバランス","換気不要"],"answer":3},
    {"question":"危険物保安監督者の選任義務の典型は？","choices":["合計倍数150以上など","常に必要","研究室でも必須","少量でも必須"],"answer":1},
    {"question":"危険物容器の材質として望ましいのは？","choices":["金属容器","薄肉ポリエチレンのみ","紙容器","木容器"],"answer":1},
    {"question":"出火時の初動として適切なのは？","choices":["状況把握→通報→初期消火","SNS投稿","写真撮影優先","放水のみ"],"answer":1},
    {"question":"ガソリン火災への水の散布が不適な理由は？","choices":["反応するため","油の浮上拡散を助長","泡が発生しないため","二酸化炭素が発生するため"],"answer":2},
    {"question":"指定数量倍数が増えると一般に必要なのは？","choices":["安全対策の強化","標識縮小","緩和措置","変化なし"],"answer":1},
    {"question":"『屋内タンクの換気』で重要なのは？","choices":["排気のみ","遮光のみ","給気・排気のバランス","冷却のみ"],"answer":3},
]

# ===== ユーティリティ =====
def normalize_choice(s: str) -> int | None:
    s = s.strip()
    m = {"①":"1","②":"2","③":"3","④":"4","１":"1","２":"2","３":"3","４":"4"}
    s = m.get(s, s)
    return int(s) if s in ("1","2","3","4") else None

def make_question():
    qid = random.randrange(len(Q))
    q = Q[qid]
    text = (
        f"Q{st_placeholder}: {q['question']}\n"
        f"① {q['choices'][0]}\n"
        f"② {q['choices'][1]}\n"
        f"③ {q['choices'][2]}\n"
        f"④ {q['choices'][3]}"
    )
    return qid, text, q["choices"], q["answer"]

def send_quiz(user_id: str, reply_token: str):
    st = get_or_init_state(user_id)
    qid = random.randrange(len(Q))
    q = Q[qid]
    st["qid"] = qid
    st["answer"] = q["answer"]
    text = (
        f"Q{st['count']+1}/{st['target']}: {q['question']}\n"
        f"① {q['choices'][0]}\n"
        f"② {q['choices'][1]}\n"
        f"③ {q['choices'][2]}\n"
        f"④ {q['choices'][3]}"
    )
    line_bot_api.reply_message(
        reply_token,
        TextSendMessage(text=text, quick_reply=qr_choices(q["choices"]))
    )

def judge_and_reply(user_id: str, reply_token: str, user_input: str):
    st = get_or_init_state(user_id)
    if st.get("answer") is None:
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text="先に『問題』または『次の問題』で出題してね。", quick_reply=qr_menu())
        )
        return

    chosen = normalize_choice(user_input)
    if chosen is None:
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text="①〜④で答えてね。", quick_reply=qr_menu())
        )
        return

    # 採点
    correct_flag = (chosen == st["answer"])
    save_result(user_id, st["qid"], correct_flag)
    st["count"] += 1
    if correct_flag:
        st["correct"] += 1

    # メッセージ
    marks = ["①","②","③","④"]
    q = Q[st["qid"]]
    base = "⭕ 正解！" if correct_flag else f"❌ 不正解… 正解は {marks[q['answer']-1]}『{q['choices'][q['answer']-1]}』"

    # 10問ごと or 最終で途中成績/最終成績
    summary = ""
    if st["count"] % 10 == 0 or st["count"] >= st["target"]:
        rate = round(st["correct"] / st["count"] * 100, 1)
        summary = f"\n— 途中成績 —\n{st['count']}/{st['target']}問中：{st['correct']}問 正解（{rate}%）"
    if st["count"] >= st["target"]:
        final_rate = round(st["correct"] / st["target"] * 100, 1)
        summary += f"\n\n✅ 最終成績：{st['correct']}/{st['target']}問 正解（{final_rate}%）\nセッションはリセットしました。"
        reset_session(user_id)
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text=base + summary, quick_reply=qr_menu())
        )
        return

    line_bot_api.reply_message(
        reply_token,
        TextSendMessage(text=base + summary, quick_reply=qr_menu())
    )
    # 次の出題に備えて答えだけクリア
    st["qid"] = None
    st["answer"] = None

# ===== health =====
@app.get("/health")
def health():
    return {"status": "ok"}

# ===== webhook =====
@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    try:
        events = parser.parse(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if not isinstance(event, MessageEvent): continue
        if not isinstance(event.message, TextMessage): continue

        user_id = event.source.user_id
        text = event.message.text.strip()

        if text in ("問題","次の問題","クイズ","quiz"):
            send_quiz(user_id, event.reply_token); continue

        if text in ("ステータス","状態","進捗"):
            st = get_or_init_state(user_id)
            if st["count"] == 0:
                msg = f"まだ未回答。目標 {st['target']}問。『問題』で開始！"
            else:
                rate = round(st["correct"]/st["count"]*100,1)
                msg = f"途中成績：{st['count']}/{st['target']}問中 {st['correct']}問 正解（{rate}%）"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg, quick_reply=qr_menu()))
            continue

        if text in ("リセット","セッションリセット"):
            reset_session(user_id)
            line_bot_api.reply_message(event.reply_token,
                TextSendMessage(text="セッションをリセットしました。『問題』で再開できます。", quick_reply=qr_menu()))
            continue

        if text in ("成績確認","成績","スコア"):
            total, ok, rate = get_stats(user_id)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"累積成績：{ok}/{total}問 正解（{rate}%）", quick_reply=qr_menu())
            )
            continue

        if text in ("ヘルプ","使い方","help"):
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=HELP_TEXT, quick_reply=qr_menu()))
            continue

        if normalize_choice(text) is not None:
            judge_and_reply(user_id, event.reply_token, text)
            continue

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="『問題』『次の問題』『①〜④で回答』『ステータス』『成績確認』『リセット』が使えます。", quick_reply=qr_menu())
        )

    return JSONResponse({"status":"ok"})
