# -*- coding: utf-8 -*-
# 乙4クイズ LINE Bot（FastAPI版・完成）
# - /healthあり（Renderのヘルスチェック用）
# - 初回＆リセット時にヘルプ自動表示
# - 50問収録（cat: 法令 / 物理化学 / 性状消火）
# - 25問/50問で総括表示
# - 回答後のクイックリプライは「リセット」「ヘルプ」のみ
# - 出題モード切替：「法令」「物理」「性状」「ランダム」
# - 紙吹雪などの演出なし

import os
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from linebot import LineBotApi, WebhookHandler
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction,
)

app = FastAPI()

# ====== LINE 環境変数 ======
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    print("!!! Set LINE_CHANNEL_ACCESS_TOKEN / LINE_CHANNEL_SECRET !!!")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

TOTAL = 50
MID = 25

# ====== クイックリプライ（回答後はリセット/ヘルプのみ） ======
def quick_reset_help() -> QuickReply:
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="リセット", text="リセット")),
        QuickReplyButton(action=MessageAction(label="ヘルプ",   text="ヘルプ")),
    ])

# ====== 50問（cat: 法令 / 物理化学 / 性状消火） ======
# 正答は "a": "1"～"4" の文字列
questions = [
    {"q": "ガソリンは第何類？\n1 第1類\n2 第2類\n3 第4類\n4 第6類", "a": "3", "cat": "性状消火"},
    {"q": "灯油はどれに分類？\n1 第1石油類\n2 アルコール類\n3 第2石油類\n4 危険物ではない", "a": "3", "cat": "性状消火"},
    {"q": "軽油の引火点の目安は？\n1 −20℃以下\n2 21～70℃\n3 70℃以上\n4 引火点なし", "a": "2", "cat": "物理化学"},
    {"q": "第1石油類の指定数量は？\n1 100L\n2 200L\n3 400L\n4 1000L", "a": "2", "cat": "法令"},
    {"q": "アルコール類の例は？\n1 メタノール\n2 軽油\n3 灯油\n4 潤滑油", "a": "1", "cat": "性状消火"},
    {"q": "第2石油類（水溶性）は表示で何を付記？\n1 水溶性\n2 非水溶性\n3 無水\n4 無害", "a": "1", "cat": "法令"},
    {"q": "乙4で取り扱わないのは？\n1 第4類\n2 第1類\n3 第6類\n4 第2類", "a": "2", "cat": "法令"},
    {"q": "引火点の定義は？\n1 自然発火温度\n2 着火で継続燃焼する最低温度\n3 沸点\n4 凝固点", "a": "2", "cat": "物理化学"},
    {"q": "発火点は？\n1 火源なしで燃え始める温度\n2 点火すると消える温度\n3 沸点\n4 凝固点", "a": "1", "cat": "物理化学"},
    {"q": "第3石油類の代表は？\n1 ガソリン\n2 軽油\n3 クレオソート油\n4 エタノール", "a": "3", "cat": "性状消火"},
    {"q": "水溶性第1石油類は？\n1 ベンゼン\n2 酢酸エチル\n3 アセトン\n4 トルエン", "a": "3", "cat": "性状消火"},
    {"q": "危険物の性状で誤りは？\n1 引火点が低いほど危険性高い\n2 蒸気比重が空気より大きいと低所に滞留\n3 蒸気圧が高いほど蒸気は少ない\n4 蒸気は着火源があると燃える", "a": "3", "cat": "物理化学"},
    {"q": "指定数量以上の貯蔵は？\n1 届出不要\n2 消防法の許可等が必要\n3 保健所許可\n4 警察届出", "a": "2", "cat": "法令"},
    {"q": "危険物施設の標識で必要なのは？\n1 危険物の類別\n2 所有者住所\n3 消費税番号\n4 電力会社名", "a": "1", "cat": "法令"},
    {"q": "表示で正しいのは？\n1 赤地『火気厳禁』\n2 黄地『高電圧』\n3 青地『徐行』\n4 緑地『安全』", "a": "1", "cat": "法令"},
    {"q": "静電気対策で不適切は？\n1 アース\n2 導電性床\n3 乾燥させる\n4 導電性ホース", "a": "3", "cat": "物理化学"},
    {"q": "油火災に適する消火器は？\n1 水\n2 泡\n3 CO2は不適\n4 蒸気", "a": "2", "cat": "性状消火"},
    {"q": "泡消火の主効果は？\n1 冷却\n2 窒息・遮断\n3 希釈\n4 連鎖反応抑制のみ", "a": "2", "cat": "性状消火"},
    {"q": "CO2消火の主効果は？\n1 冷却と窒息\n2 希釈のみ\n3 発火点上昇\n4 泡で覆う", "a": "1", "cat": "性状消火"},
    {"q": "漏えい時の初期対応で不適切は？\n1 着火源除去\n2 風上から接近\n3 水で一気に流す\n4 通報・退避", "a": "3", "cat": "法令"},
    {"q": "蒸気比重>1 の蒸気は？\n1 上層に溜まる\n2 低所に溜まる\n3 上昇拡散\n4 無臭になる", "a": "2", "cat": "物理化学"},
    {"q": "ブリーザーの目的は？\n1 圧力変動調整\n2 消火\n3 蒸気回収\n4 着火", "a": "1", "cat": "性状消火"},
    {"q": "移送で不適切は？\n1 金属配管で接地\n2 プラ容器同士の手持ち移送\n3 金属ホースで接地\n4 液面下注入", "a": "2", "cat": "物理化学"},
    {"q": "第1石油類は？\n1 ガソリン\n2 灯油\n3 軽油\n4 重油", "a": "1", "cat": "性状消火"},
    {"q": "アルコール類の指定数量は？\n1 100L\n2 200L\n3 400L\n4 600L", "a": "3", "cat": "法令"},
    {"q": "保安教育の対象は？\n1 取扱者のみ\n2 関係従業員\n3 署長\n4 警備員のみ", "a": "2", "cat": "法令"},
    {"q": "泡原液の希釈は？\n1 水で希釈\n2 溶剤希釈\n3 原液のまま\n4 アルコール希釈", "a": "1", "cat": "性状消火"},
    {"q": "ATC泡の用途は？\n1 非水溶性のみ\n2 水溶性にも有効\n3 気体火災専用\n4 金属火災専用", "a": "2", "cat": "性状消火"},
    {"q": "Naと接触不可は？\n1 水\n2 窒素\n3 乾燥砂\n4 CO2", "a": "1", "cat": "性状消火"},
    {"q": "運搬容器の表示で必須は？\n1 品名・類別\n2 従業員名\n3 価格\n4 取扱所図面", "a": "1", "cat": "法令"},
    {"q": "自然発火になりにくいのは？\n1 乾性油ウエス堆積\n2 石炭大量堆積\n3 ガソリン密閉保管\n4 木粉堆積", "a": "3", "cat": "性状消火"},
    {"q": "アセトンの類別は？\n1 第1石油類(非水)\n2 第1石油類(水)\n3 アルコール類\n4 第2石油類", "a": "2", "cat": "性状消火"},
    {"q": "トルエンの類別は？\n1 第1石油類(非水)\n2 第1石油類(水)\n3 第2石油類\n4 アルコール類", "a": "1", "cat": "性状消火"},
    {"q": "酢酸エチルは？\n1 第1石油類(非水)\n2 第1石油類(水)\n3 第2石油類\n4 第3石油類", "a": "1", "cat": "性状消火"},
    {"q": "メタノールは？\n1 第1石油類\n2 アルコール類\n3 第2石油類\n4 第3石油類", "a": "2", "cat": "性状消火"},
    {"q": "流出油火災の基本対応は？\n1 水で散布\n2 泡で覆う\n3 加温\n4 砂を禁ず", "a": "2", "cat": "性状消火"},
    {"q": "静電気対策で有効は？\n1 低湿度\n2 アース・等電位化\n3 絶縁手袋多用\n4 樹脂容器間移送", "a": "2", "cat": "物理化学"},
    {"q": "自然発火点が低いのは一般に？\n1 ガソリン\n2 灯油\n3 軽油\n4 重油", "a": "1", "cat": "物理化学"},
    {"q": "運搬積載量を定める法は？\n1 消防法\n2 道路交通法\n3 安衛法\n4 建築基準法", "a": "2", "cat": "法令"},
    {"q": "指定数量未満でも必要なのは？\n1 何も不要\n2 一部規制（保管等）\n3 必ず許可\n4 税務届出", "a": "2", "cat": "法令"},
    {"q": "可燃蒸気は一般に？\n1 空気より軽い\n2 同等\n3 空気より重い\n4 同じ", "a": "3", "cat": "物理化学"},
    {"q": "混合で避けるべきは？\n1 類似性状\n2 水溶性と非水溶性の不用意混合\n3 同フラッシュ\n4 同比重", "a": "2", "cat": "性状消火"},
    {"q": "換気の主目的は？\n1 湿度低減\n2 蒸気濃度低減\n3 温度差低減\n4 圧力損失低減", "a": "2", "cat": "性状消火"},
    {"q": "発火点に影響するのは？\n1 容器色\n2 気流・酸素濃度\n3 密度\n4 比重", "a": "2", "cat": "物理化学"},
    {"q": "軽油の類別は？\n1 第1石油類\n2 第2石油類\n3 第3石油類\n4 第4石油類", "a": "2", "cat": "性状消火"},
    {"q": "潤滑油の類別は？\n1 第1石油類\n2 第2石油類\n3 第3石油類\n4 第4石油類", "a": "3", "cat": "性状消火"},
    {"q": "掲示義務がないのは？\n1 類別\n2 禁止事項\n3 取扱者氏名\n4 避難経路図", "a": "4", "cat": "法令"},
    {"q": "引火点が最も低いのは？\n1 ガソリン\n2 灯油\n3 軽油\n4 クレオソート油", "a": "1", "cat": "物理化学"},
    {"q": "服装で不適切は？\n1 帯電防止服\n2 静電靴\n3 化繊フリース\n4 綿作業着", "a": "3", "cat": "性状消火"},
    {"q": "受入時の基本動作は？\n1 先にマンホール開放\n2 まず接地(アース)\n3 先にバルブ開放\n4 周囲喫煙所設置", "a": "2", "cat": "法令"},
    {"q": "指定数量以上の取扱所に必須の資格者は？\n1 危険物取扱者\n2 毒物劇物取扱者\n3 電気主任技術者\n4 ボイラー技士", "a": "1", "cat": "法令"},
]

# ====== 進捗管理 ======
# user_id -> {"q_index": int, "score": int, "mode": "ランダム/法令/物理/性状"}
progress: Dict[str, Dict[str, Any]] = {}

def init_session(uid: str):
    progress[uid] = {"q_index": 0, "score": 0, "mode": "ランダム"}

def pick_index(state: Dict[str, Any]) -> Optional[int]:
    """モードに応じて次に出すインデックスを返す。なければ None。"""
    i = state["q_index"]
    if i >= TOTAL:
        return None
    mode = state.get("mode", "ランダム")
    if mode == "ランダム":
        return i
    want = {"法令": "法令", "物理": "物理化学", "性状": "性状消火"}.get(mode)
    # 現在位置以降で該当カテゴリを探す
    for j in range(i, len(questions)):
        if questions[j].get("cat") == want:
            return j
    # なければ通常の順番
    return i

# ====== ヘルプ送信 ======
def send_help(reply_token: str):
    help_text = (
        "📘 使い方\n"
        "・「開始」→ 出題スタート\n"
        "・「次の問題」→ 次の問題を出題\n"
        "・「リセット」→ 最初からやり直し\n\n"
        "🎯 出題モード切替（トークで送るだけ）\n"
        "・「法令」→ 法令分野だけ出題\n"
        "・「物理」→ 物理化学分野だけ出題\n"
        "・「性状」→ 性状・消火分野だけ出題\n"
        "・「ランダム」→ 全体からランダム出題（通常）\n\n"
        "📝 成績表示\n"
        f"・{MID}問目と{TOTAL}問目で総括を表示\n"
    )
    line_bot_api.reply_message(reply_token, TextSendMessage(text=help_text))

# ====== ヘルスチェック ======
@app.get("/health")
def health():
    return {"status": "ok"}

# ====== LINE Webhook ======
@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode("utf-8")
    try:
        handler.handle(body, signature)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid signature or parse error")
    return JSONResponse({"ok": True})

@handler.add(MessageEvent, message=TextMessage)
def on_message(event: MessageEvent):
    uid = event.source.user_id
    text = (event.message.text or "").strip()

    first_time = False
    if uid not in progress:
        init_session(uid)
        first_time = True

    st = progress[uid]

    # 初回はヘルプを自動表示して終了
    if first_time:
        send_help(event.reply_token)
        return

    # ===== コマンド =====
    if text in ("リセット", "reset"):
        init_session(uid)
        send_help(event.reply_token)  # リセット時もヘルプ自動表示
        return

    if text in ("ヘルプ", "help", "？", "?"):
        send_help(event.reply_token)
        return

    if text in ("法令", "物理", "性状", "ランダム"):
        st["mode"] = text
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"出題モードを「{text}」に変更しました。")
        )
        return

    if text in ("開始", "次の問題"):
        idx = pick_index(st)
        if idx is None:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="✅ 全問題終了。「リセット」で再挑戦できます。")
            )
            return
        qno = st["q_index"] + 1
        q = questions[idx]["q"]
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"Q{qno}/{TOTAL}\n{q}")
        )
        return

    # ===== 回答（1～4・全角対応） =====
    if text in ("1", "2", "3", "4", "１", "２", "３", "４"):
        trans = str.maketrans("１２３４", "1234")
        ans = text.translate(trans)

        idx = pick_index(st)
        if idx is None:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="✅ 全問題終了。「リセット」で再挑戦できます。")
            )
            return

        correct = questions[idx]["a"]
        ok = (ans == correct)
        if ok:
            st["score"] += 1
        st["q_index"] += 1

        msg = "⭕ 正解！" if ok else f"❌ 不正解… 正解は {correct}"

        # 総括（25問・50問）
        if st["q_index"] in (MID, TOTAL):
            total = st["q_index"]
            rate = st["score"] / total * 100
            msg += f"\n📊 {total}問終了：{st['score']}/{total}（{rate:.1f}%）"

        # 次へ or 終了文
        if st["q_index"] < TOTAL:
            msg += f"\n\n『次の問題』で続きへ。"
        else:
            msg += "\n✅ 全問題終了。「リセット」で最初から。"

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=msg, quick_reply=quick_reset_help())
        )
        return

    # ===== デフォルト応答 =====
    send_help(event.reply_token)
