# =========================
#  Hazmat-4 (乙4) LINE Bot
#  - 出題時に ①②③④ クイックリプライ
#  - 回答後は「リセット」「ヘルプ」だけ
#  - 25問/50問で進捗サマリ
#  - /health あり
# =========================

import os
import random
from typing import Dict, Any, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse

from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)

# ---- 環境変数（Render / .env などで設定）----
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
if not CHANNEL_SECRET or not CHANNEL_ACCESS_TOKEN:
    # デプロイ時に気づけるように起動直後から分かりやすく
    print("!! LINE_CHANNEL_SECRET / LINE_CHANNEL_ACCESS_TOKEN が未設定です。")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(CHANNEL_SECRET)

# ---- FastAPI ----
app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

# ========= 質問データ（50問） =========
# 形式: {"q": "問題文...\n1 〜\n2 〜\n3 〜\n4 〜", "ans": 2, "exp": "解説"}
# ※実運用では過去問に合わせて自由に差し替えてください
questions = [
    # --- 法令系（例）---
    {"q": "第1石油類の指定数量は？\n1 100L\n2 200L\n3 400L\n4 1000L", "ans": 2, "exp": "第1石油類の指定数量は200L。"},
    {"q": "第2石油類（水溶性）の指定数量は？\n1 1000L\n2 2000L\n3 4000L\n4 6000L", "ans": 2, "exp": "第2石油類（水溶性）は2000L。"},
    {"q": "保安距離の目的は？\n1 装飾\n2 飛散・揮発抑制と安全注ぎ\n3 重量増\n4 保温", "ans": 2, "exp": "障害や危険拡大防止のための距離。"},
    {"q": "貯蔵取扱いが指定数量以上のとき必要なものは？\n1 届出不要\n2 消防法の許可等\n3 所轄警察のみ\n4 厚労省のみ", "ans": 2, "exp": "消防機関の許可等が必要。"},
    {"q": "危険物施設の規制根拠法は？\n1 労基法\n2 消防法\n3 警職法\n4 建築基準法", "ans": 2, "exp": "危険物は消防法による規制。"},
    # --- 物理化学（例）---
    {"q": "引火点とは？\n1 自然発火する温度\n2 火源で着火する最低温度\n3 水の沸点\n4 凝固点", "ans": 2, "exp": "引火点=可燃性蒸気が火源で着火する最低温度。"},
    {"q": "発火点とは？\n1 自然発火する温度\n2 引火点より低い\n3 沸点\n4 凝固点", "ans": 1, "exp": "発火点=火源なしで自然発火する温度。"},
    {"q": "蒸気密度が1より大きい可燃蒸気の挙動は？\n1 上方へ滞留\n2 下方に滞留しやすい\n3 その場に留まる\n4 挙動しない", "ans": 2, "exp": "空気より重いと低所に滞留しやすい。"},
    {"q": "可燃範囲が広いほど？\n1 危険性は低い\n2 危険性は高い\n3 変わらない\n4 取扱量に依存", "ans": 2, "exp": "可燃範囲が広い=着火しやすく危険。"},
    {"q": "静電気対策で適切なのは？\n1 断熱\n2 接地（アース）\n3 加圧\n4 水冷", "ans": 2, "exp": "接地・等電位化で放電を防ぐ。"},
    # --- 性質・消火（例）---
    {"q": "アルコール類に適した消火剤は？\n1 水のみ\n2 粉末・泡（アルコール耐性）\n3 二酸化炭素のみ\n4 砂のみ", "ans": 2, "exp": "水溶性なのでアルコール耐性泡・粉末が有効。"},
    {"q": "油火災の初期消火に不適切なのは？\n1 泡\n2 粉末\n3 水の直かけ\n4 CO2", "ans": 3, "exp": "水ははね飛ばし拡大の危険。"},
    {"q": "金属ナトリウム火災に適するのは？\n1 水\n2 泡\n3 乾燥砂・金属用粉末\n4 CO2", "ans": 3, "exp": "水・泡は禁忌。乾燥砂等を使用。"},
    {"q": "電気火災で感電を避ける基本は？\n1 通電のまま放水\n2 まず遮断\n3 近づかない\n4 砂のみ", "ans": 2, "exp": "まず電源遮断、絶縁消火剤を使用。"},
    {"q": "二酸化炭素消火の主作用は？\n1 冷却\n2 窒息\n3 乳化\n4 希釈", "ans": 2, "exp": "CO2は窒息効果。"},
    # ここから下はダミー（合計50問になるように追加）
] + [
    {
        "q": f"確認テスト {i}：適切なのはどれ？\n1 A\n2 B\n3 C\n4 D",
        "ans": (i % 4) + 1,
        "exp": "（ダミー）本番では過去問に置き換えてください。"
    }
    for i in range(1, 50 - 15 + 1)  # すでに15問あるので残りをダミーで埋めて50問
]

TOTAL = len(questions)  # 50

# ========= ユーザ状態 =========
# 超簡易メモリ（Render無料だと落ちると消えます。永続化はDB等を検討）
state: Dict[str, Dict[str, Any]] = {}

def get_state(uid: str) -> Dict[str, Any]:
    if uid not in state:
        state[uid] = {
            "answered": 0,       # 回答数
            "correct": 0,        # 正解数
            "asked_ids": set(),  # 出題済インデックス
            "last_q_id": None,   # 直近の出題インデックス
        }
    return state[uid]

def pick_next_question(st: Dict[str, Any]) -> Optional[int]:
    """未出題からランダムに1問選ぶ。尽きたら None。"""
    remaining = [i for i in range(TOTAL) if i not in st["asked_ids"]]
    if not remaining:
        return None
    return random.choice(remaining)

# ========= クイックリプライ =========
def quick_choices() -> QuickReply:
    """出題時の ①〜④ ボタン"""
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="①", text="1")),
        QuickReplyButton(action=MessageAction(label="②", text="2")),
        QuickReplyButton(action=MessageAction(label="③", text="3")),
        QuickReplyButton(action=MessageAction(label="④", text="4")),
    ])

def quick_reset_help() -> QuickReply:
    """回答後はリセットとヘルプのみ"""
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="リセット", text="リセット")),
        QuickReplyButton(action=MessageAction(label="ヘルプ", text="ヘルプ")),
    ])

# ========= ヘルプ =========
HELP_TEXT = (
    "📘 使い方\n"
    "・「開始」：クイズを開始\n"
    "・「次の問題」：次へ進む\n"
    "・数字「1〜4」：選択肢を回答（①②③④ボタンでもOK）\n"
    "・「成績確認」：現在の成績を表示\n"
    "・「リセット」：進捗をリセット\n\n"
    "※25問・50問で自動サマリが出ます。\n"
    "※問題文・分野バランス（法令/物化/性消）は後で過去問に合わせて差し替え可能です。"
)

def summary_text(st: Dict[str, Any], title: str = "成績") -> str:
    a = st["answered"]
    c = st["correct"]
    rate = 0 if a == 0 else round(100 * c / a, 1)
    return f"📊 {title}\n回答：{a} 問 / 正解：{c} 問（{rate}%）"

# ========= Webhook =========
@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    try:
        events = parser.parse(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for ev in events:
        if isinstance(ev, MessageEvent) and isinstance(ev.message, TextMessage):
            await handle_text(ev)

    return PlainTextResponse("OK")

# ========= 本体ロジック =========
async def handle_text(event: MessageEvent):
    uid = event.source.user_id
    text = event.message.text.strip()
    st = get_state(uid)

    # ---- コマンド類 ----
    if text in ("ヘルプ", "help", "？", "使い方"):
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=HELP_TEXT)
        )
        return

    if text in ("リセット", "reset"):
        state[uid] = {
            "answered": 0, "correct": 0, "asked_ids": set(), "last_q_id": None
        }
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="♻️ セッションをリセットしました。『開始』で再スタート！")
        )
        return

    if text in ("成績確認", "ステータス"):
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=summary_text(st, "現在の成績"))
        )
        return

    if text in ("開始", "次の問題"):
        qid = pick_next_question(st)
        if qid is None:
            # 全問出し切り
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="✅ 全て出題済みです。『リセット』で最初からやり直せます。",
                    quick_reply=quick_reset_help()
                )
            )
            return
        st["last_q_id"] = qid
        st["asked_ids"].add(qid)
        qno = st["answered"] + 1
        q = questions[qid]["q"]
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"Q{qno}/{TOTAL}\n{q}", quick_reply=quick_choices())
        )
        return

    # ---- 回答（1〜4 / ①〜④） ----
    normalized = text.replace("①", "1").replace("②", "2").replace("③", "3").replace("④", "4")
    if normalized in ("1", "2", "3", "4"):
        if st["last_q_id"] is None:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="まず『開始』で問題を表示してね。", quick_reply=quick_reset_help())
            )
            return

        choice = int(normalized)
        qid = st["last_q_id"]
        ans = questions[qid]["ans"]
        exp = questions[qid]["exp"]

        st["answered"] += 1
        correct = (choice == ans)
        if correct:
            st["correct"] += 1

        mark = "⭕ 正解！" if correct else "❌ 不正解…"
        feed = f"{mark}\n正解は {ans}。\n（補足）{exp}"

        # 25問・50問でサマリ
        extra = ""
        if st["answered"] in (25, 50):
            extra = "\n\n" + summary_text(st, f"{st['answered']}問サマリ")

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=feed + extra, quick_reply=quick_reset_help())
        )
        # 次の出題はユーザーが「次の問題」or クイックリプライで選ぶ設計
        return

    # それ以外：ヘルプへ
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="🤖 コマンドが分かりませんでした。\n『開始』『次の問題』『1〜4』『成績確認』『リセット』『ヘルプ』を試してください。")
    )
