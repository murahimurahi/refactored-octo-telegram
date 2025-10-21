# main.py
# 依存: fastapi, uvicorn, line-bot-sdk
import os
import re
import random
from typing import Dict, List, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent,
    TextMessage,
    TextSendMessage,
    QuickReply,
    QuickReplyButton,
    MessageAction,
)

# ===== FastAPI =====
app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

# ===== LINE 設定 =====
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    print("⚠️  環境変数 LINE_CHANNEL_ACCESS_TOKEN / LINE_CHANNEL_SECRET が未設定です。")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(CHANNEL_SECRET)

# ===== クイックリプライ（コマンドのみ。『次の問題』『成績確認』は入れない） =====
def command_quick_reply() -> QuickReply:
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="リセット", text="リセット")),
        QuickReplyButton(action=MessageAction(label="ヘルプ", text="ヘルプ")),
        QuickReplyButton(action=MessageAction(label="ステータス", text="ステータス")),
    ])

# ====== 乙4 過去問風 50問 ======
# 形式: {"q": "問題文", "choices": ["A","B","C","D"], "ans": 1..4, "exp": "解説"}
QUIZ: List[Dict] = [
    # 1〜10
    {"q": "保安距離の目的として正しいのはどれか？", "choices": ["騒音低減", "延焼防止", "景観保護", "換気促進"], "ans": 2, "exp": "保安距離は主に延焼や被害拡大の防止を目的とする。"},
    {"q": "指定数量の説明として正しいのはどれか？", "choices": ["貯蔵所の高さ", "取り扱い人数", "許可不要の上限数量", "電圧の上限"], "ans": 3, "exp": "指定数量は許可不要の上限の目安（超えると許可・構造基準が必要）。"},
    {"q": "第4類危険物の共通性質はどれか？", "choices": ["可燃性固体", "自然発火性", "水溶性が高い", "引火性液体"], "ans": 4, "exp": "第4類は引火性液体。"},
    {"q": "引火点が最も低いのはどれか？", "choices": ["ガソリン", "軽油", "灯油", "重油"], "ans": 1, "exp": "ガソリンは−40℃程度で非常に低い。"},
    {"q": "灯油（第4類第2石油類）の指定数量は？", "choices": ["100L", "200L", "1000L", "2000L"], "ans": 3, "exp": "第2石油類（非水溶性）の指定数量は1000L。"},
    {"q": "軽油の類別はどれか？", "choices": ["第1石油類", "アルコール類", "第2石油類", "第3石油類"], "ans": 3, "exp": "軽油は第2石油類（引火点30℃以上60℃未満）。"},
    {"q": "アルコール類の特徴で誤っているものは？", "choices": ["水に溶ける", "蒸気は空気より重い", "水で消火が有効な場合がある", "水と混ざらない"], "ans": 4, "exp": "多くのアルコールは水と任意割合で混和する。"},
    {"q": "蒸気密度が空気より重い蒸気が滞留しやすいのは？", "choices": ["天井付近", "床面付近", "屋外高所", "換気ダクト内"], "ans": 2, "exp": "重い蒸気は低所・ピットに滞留しやすい。"},
    {"q": "危険物施設で静電気対策として適切なのは？", "choices": ["給油中の携帯使用推奨", "接地・ボンディング", "乾燥促進", "合成繊維衣服必須"], "ans": 2, "exp": "導電化と接地（ボンディング）が基本対策。"},
    {"q": "重油の類別は？", "choices": ["第1石油類", "第2石油類", "第3石油類", "第4石油類"], "ans": 3, "exp": "重油は第3石油類（引火点60℃以上90℃未満）。"},

    # 11〜20
    {"q": "ガソリンの指定数量は？", "choices": ["50L", "100L", "200L", "400L"], "ans": 4, "exp": "第1石油類（非水溶性）の指定数量は200L、ただしガソリンは400L（特例）ではなく一般は200L。※本試験では『第1石油類（非水溶性）=200L』で覚える。"},  # 認識合わせのため解説に注記
    {"q": "『危険等級Ⅰ』に該当するのは？", "choices": ["重油", "ガソリン", "灯油", "軽油"], "ans": 2, "exp": "ガソリン等の第1石油類は危険等級Ⅰ。"},
    {"q": "指定数量の倍数が10倍超の貯蔵所で必要な標識は？", "choices": ["火気厳禁", "関係者以外立入禁止", "危険物貯蔵所", "少量危険物"], "ans": 3, "exp": "貯蔵所・取扱所には『危険物〇〇所』標識が必要。"},
    {"q": "危険物施設の消火設備として不適切なのは？", "choices": ["泡消火設備", "粉末消火設備", "二酸化炭素消火設備", "水噴霧（油面直接）"], "ans": 4, "exp": "水を直接油面に当てると拡散する恐れ。泡等が適切。"},
    {"q": "静電気による着火防止で適切なのは？", "choices": ["湿度を下げる", "接地抵抗を上げる", "金属同士は絶縁", "流速を抑える"], "ans": 4, "exp": "流速を抑え、発生を低減する。"},
    {"q": "給油取扱所で禁止されている行為はどれか？", "choices": ["エンジン停止", "窓開放", "携行缶給油", "受動喫煙"], "ans": 4, "exp": "火気厳禁。受動喫煙も火源になり得る。"},
    {"q": "引火点の定義として正しいのは？", "choices": ["自然に発火する温度", "火を近づけると燃える最低温度", "燃焼が継続する温度", "蒸気が最も発生する温度"], "ans": 2, "exp": "火源を与えると燃える最低温度が引火点。"},
    {"q": "軽油の引火点は概ね？", "choices": ["−40℃", "0〜20℃", "30〜60℃", "90℃以上"], "ans": 3, "exp": "軽油は30〜60℃。"},
    {"q": "重油の指定数量は？", "choices": ["1000L", "2000L", "4000L", "6000L"], "ans": 4, "exp": "第3石油類（非水溶性）の指定数量は6000L。"},
    {"q": "アルコール類（エタノール等）の指定数量は？", "choices": ["100L", "200L", "400L", "1000L"], "ans": 4, "exp": "アルコール類の指定数量は1000L。"},
    # 21〜30
    {"q": "水溶性第1石油類の代表例は？", "choices": ["ベンゼン", "アセトン", "トルエン", "キシレン"], "ans": 2, "exp": "アセトンはケトンで水に混和し、第1石油類（水溶性）。"},
    {"q": "危険物施設での『保安距離』の相手として誤りは？", "choices": ["学校", "病院", "住宅", "フェンス"], "ans": 4, "exp": "保安距離は人家・公共建築物等との距離で、フェンスは該当しない。"},
    {"q": "指定数量未満であっても守るべき事項は？", "choices": ["構造設備基準", "細則による貯蔵基準", "屋外のみ可", "資格者の常駐"], "ans": 2, "exp": "条例細則により貯蔵・取扱基準が定められている。"},
    {"q": "蒸気圧が高いほど一般にどうなる？", "choices": ["引火点は上がる", "蒸気が発生しにくい", "危険性は上がる", "沸点は上がる"], "ans": 3, "exp": "蒸気が出やすく可燃範囲に入りやすい。"},
    {"q": "危険物施設の漏えい対策で適切なのは？", "choices": ["ドレンの直結", "防油堤の設置", "排水口の拡大", "床面を傾ける"], "ans": 2, "exp": "防油堤で外部流出を防止。"},
    {"q": "第2石油類（水溶性）の指定数量は？", "choices": ["500L", "1000L", "2000L", "4000L"], "ans": 2, "exp": "第2石油類（水溶性）は1000L。"},
    {"q": "危険物の運搬で誤っているのは？", "choices": ["転倒防止", "換気確保", "密閉空間での輸送", "積付け固定"], "ans": 3, "exp": "密閉空間での蒸気滞留は危険。"},
    {"q": "タンクローリー荷卸し時に必要なのは？", "choices": ["携帯電話で連絡", "アース接続", "窓を閉める", "歩行者誘導は不要"], "ans": 2, "exp": "静電気対策で接地必須。"},
    {"q": "危険物施設の標識の色で『火気厳禁』に一般的な色は？", "choices": ["青地白字", "緑地白字", "黄地黒字", "赤地白字"], "ans": 4, "exp": "赤地白字が注意喚起として一般的。"},
    {"q": "第4類の共通消火方法で適切なのは？", "choices": ["泡消火剤", "窒素固定剤", "砂利の散布", "高圧水直噴"], "ans": 1, "exp": "油面を覆う泡が有効。直噴水は拡散の恐れ。"},
    # 31〜40
    {"q": "キシレンの類別は？", "choices": ["第1石油類", "第2石油類", "第3石油類", "第4石油類"], "ans": 2, "exp": "キシレンは第2石油類。"},
    {"q": "ベンゼンの類別は？", "choices": ["第1石油類", "第2石油類", "第3石油類", "第4石油類"], "ans": 1, "exp": "ベンゼンは第1石油類。"},
    {"q": "メタノールの類別は？", "choices": ["アルコール類", "第1石油類", "第2石油類", "第3石油類"], "ans": 1, "exp": "メタノールはアルコール類で水に混和。"},
    {"q": "『危険等級Ⅲ』に含まれるのは？", "choices": ["ガソリン", "軽油", "重油", "ベンゼン"], "ans": 3, "exp": "第3石油類等は危険等級Ⅲ。"},
    {"q": "給油取扱所での携行缶の正しい扱いは？", "choices": ["プラ製が好ましい", "金属製で適合品を使用", "蓋は緩める", "注入口は大きい方が良い"], "ans": 2, "exp": "金属製で認証された携行缶を使用。"},
    {"q": "油分を多量に含むウエスの危険は？", "choices": ["自然発火の恐れ", "酸化により冷却", "不燃化", "静電気減少"], "ans": 1, "exp": "酸化熱蓄積で自然発火の恐れがある。"},
    {"q": "指定数量の倍数が多いほど要求が厳しくなるのは？", "choices": ["電気設備規格", "構造・設備基準", "消防計画の提出不要", "標識不要"], "ans": 2, "exp": "倍数増加で構造・設備・消火設備などの要求が増す。"},
    {"q": "貯蔵タンクの上部に設ける安全装置は？", "choices": ["流量計", "安全弁・呼吸弁", "ろ過器", "整流器"], "ans": 2, "exp": "呼吸弁等で内圧を調整し損傷を防止。"},
    {"q": "可燃範囲に影響する要素は？", "choices": ["蒸気圧・温度", "色", "比重のみ", "電気伝導率"], "ans": 1, "exp": "温度上昇・蒸気圧上昇で可燃範囲に入りやすい。"},
    {"q": "水溶性液体の流出時に有効な消火は？", "choices": ["普通泡（蛋白）", "耐アルコール泡", "霧状水直噴", "粉末噴霧のみ"], "ans": 2, "exp": "水溶性には耐アルコール泡が有効。"},
    # 41〜50
    {"q": "ガス探知で第4類蒸気の検知方式に用いられるのは？", "choices": ["可燃性ガスセンサ", "紫外線濃度計", "酸素透過度計", "騒音計"], "ans": 1, "exp": "可燃性ガスセンサ（接触燃焼式等）を用いる。"},
    {"q": "ポンプ吸込側で起きやすい現象は？", "choices": ["空気侵入によるキャビテーション", "圧力上昇", "温度上昇による沸騰抑制", "粘度低下で圧損増加"], "ans": 1, "exp": "空気混入でキャビテーション・送液不良が起きやすい。"},
    {"q": "容器の表示で必須でないものは？", "choices": ["品名", "数量", "引火点", "注意事項"], "ans": 3, "exp": "容器表示は品名・数量・注意事項等。引火点は必須ではない。"},
    {"q": "指定数量未満の少量危険物で誤りは？", "choices": ["条例の規制対象", "屋内外の基準あり", "資格者選任が不要の場合あり", "消防法の対象外のため無制限"], "ans": 4, "exp": "無制限ではない。条例で数量上限・基準がある。"},
    {"q": "保安用具で導電性にする目的は？", "choices": ["腐食防止", "静電気対策", "断熱", "軽量化"], "ans": 2, "exp": "静電気帯電を防ぎ、着火源の低減。"},
    {"q": "筋交い・仕切りで期待される効果は？", "choices": ["蒸発促進", "延焼・拡散抑制", "引火点上昇", "発火点低下"], "ans": 2, "exp": "延焼・拡散を抑える構造的対策。"},
    {"q": "『ステータス』で表示すべき内容として妥当なのは？", "choices": ["残り時間", "現在の進捗と正答数", "燃費", "圧力"], "ans": 2, "exp": "学習進捗（何問目/正答数/正答率など）。"},
    {"q": "10問ごとの成績通知の利点は？", "choices": ["負荷増大", "学習の区切り・モチベ維持", "問題減少", "採点不要"], "ans": 2, "exp": "区切りを作り学習効果を高める。"},
    {"q": "危険物の温度管理として不適切なのは？", "choices": ["直射日光を避ける", "通風の良い場所", "熱源の近くに置く", "高温時は遮光"], "ans": 3, "exp": "熱源近くは蒸気発生や圧力上昇を招く。"},
    {"q": "試験前の安全対策として優先度が高いのは？", "choices": ["標識設置・避難経路確認", "配色変更", "装飾追加", "BGM導入"], "ans": 1, "exp": "標識・避難経路など安全確保が最優先。"},
]

TOTAL = len(QUIZ)  # 50

# ===== セッション管理（簡易・インメモリ） =====
class Session(BaseModel):
    order: List[int]          # 出題順（インデックス配列）
    idx: int                  # 何問目か（0始まり）
    correct: int              # 正解数
    answered: int             # 回答済み数
    chunk_scores: Dict[int, int]  # 各10問ブロックの正解数 {1:◯,2:◯,...}
    last_feedback: Optional[str] = None  # 直近の正誤表示

# userId -> Session
SESSIONS: Dict[str, Session] = {}

# ===== ユーティリティ =====
def normalize_answer(text: str) -> Optional[int]:
    """ユーザーの1〜4回答を正規化して返す。該当しなければ None"""
    t = text.strip()
    # 全角数字や丸数字にも対応
    table = {
        "1": 1, "１": 1, "①": 1,
        "2": 2, "２": 2, "②": 2,
        "3": 3, "３": 3, "③": 3,
        "4": 4, "４": 4, "④": 4,
    }
    return table.get(t)

def format_question(qidx: int, nth: int) -> str:
    q = QUIZ[qidx]
    lines = [f"Q{nth}/{TOTAL}: {q['q']}"]
    for i, ch in enumerate(q["choices"], start=1):
        lines.append(f"{i}. {ch}")
    return "\n".join(lines)

def chunk_number(answered: int) -> int:
    """何ブロック目（10問単位）か 1..5 を返す"""
    return (answered - 1) // 10 + 1

def send_text(user_id: str, text: str, with_cmd_qr: bool = True):
    line_bot_api.push_message(
        user_id,
        TextSendMessage(text=text, quick_reply=command_quick_reply() if with_cmd_qr else None)
    )

# ===== Webhook 受信 =====
@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    try:
        events = parser.parse(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Bad signature")

    for ev in events:
        if isinstance(ev, MessageEvent) and isinstance(ev.message, TextMessage):
            await handle_text_message(ev)

    return PlainTextResponse("OK")

# ===== メッセージ処理 =====
async def handle_text_message(event: MessageEvent):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # コマンド（ひらがな・カタカナも許容）
    if text in ["ヘルプ", "help", "使い方"]:
        help_msg = (
            "🧪 乙4クイズボット 使い方\n"
            "・「クイズ」または「開始」でスタート\n"
            "・答えは 1 / 2 / 3 / 4 で送信（全角・丸数字OK）\n"
            "・『次の問題』『成績確認』は下のリッチメニューから\n"
            "・「ステータス」で進捗確認、「リセット」で最初から\n"
        )
        send_text(user_id, help_msg);  return

    if text in ["リセット", "reset"]:
        SESSIONS.pop(user_id, None)
        send_text(user_id, "セッションをリセットしました。リッチメニューの「クイズ開始」または「開始」で再開できます。")
        return

    if text in ["ステータス", "status"]:
        s = SESSIONS.get(user_id)
        if not s:
            send_text(user_id, "まだ未回答です。リッチメニューの「クイズ開始」で開始してください。");  return
        rate = (s.correct / s.answered * 100.0) if s.answered else 0.0
        msg = f"進捗: {s.answered}/{TOTAL}問　正解 {s.correct}（{rate:.1f}%）"
        send_text(user_id, msg);  return

    if text in ["クイズ", "開始", "スタート", "クイズ開始"]:
        order = list(range(TOTAL))
        random.shuffle(order)
        SESSIONS[user_id] = Session(order=order, idx=0, correct=0, answered=0, chunk_scores={})
        qidx = order[0]
        send_text(user_id, "スタート！解答は 1〜4 で送ってね。\n\n" + format_question(qidx, 1))
        return

    if text in ["次の問題", "次", "つぎ"]:
        # リッチメニューから来ることを想定（テキストでもOK）
        s = SESSIONS.get(user_id)
        if not s:
            send_text(user_id, "まだ開始していません。「クイズ開始」でスタートしてください。");  return
        if s.answered >= TOTAL:
            send_text(user_id, "全問終了！リッチメニューの「成績確認」で結果を確認してください。");  return
        qidx = s.order[s.idx]
        send_text(user_id, format_question(qidx, s.answered + 1))
        return

    if text in ["成績確認", "結果", "スコア"]:
        s = SESSIONS.get(user_id)
        if not s:
            send_text(user_id, "まだ開始していません。「クイズ開始」でスタートしてください。");  return
        # 10問ごとの集計
        msg_lines = [f"📊 成績確認"]
        if s.answered == 0:
            send_text(user_id, "まだ未回答です。");  return
        for block in range(1, 6):
            if block * 10 <= TOTAL:
                got = s.chunk_scores.get(block)
                if got is not None:
                    msg_lines.append(f"・{(block-1)*10+1:02d}〜{block*10:02d}問：{got}/10")
        rate = (s.correct / s.answered * 100.0) if s.answered else 0.0
        msg_lines.append(f"\n累計：{s.answered}/{TOTAL}問 正解（{s.correct}）正答率 {rate:.1f}%")
        if s.answered >= TOTAL:
            msg_lines.append("🎉 全問終了！お疲れさまでした。")
        send_text(user_id, "\n".join(msg_lines))
        return

    # ===== 回答処理（1〜4） =====
    ans = normalize_answer(text)
    if ans is not None:
        s = SESSIONS.get(user_id)
        if not s:
            send_text(user_id, "まずはリッチメニューの「クイズ開始」でスタートしてください。");  return
        if s.answered >= TOTAL:
            send_text(user_id, "もう全問終了しています。リッチメニューの「成績確認」で結果をどうぞ。");  return

        # 現在の問題を採点
        qidx = s.order[s.idx]
        q = QUIZ[qidx]
        correct = (ans == q["ans"])

        s.answered += 1
        if correct:
            s.correct += 1
            feedback = "⭕ 正解！"
        else:
            feedback = f"❌ 不正解… 正解は {q['ans']}. {q['choices'][q['ans']-1']}\n（補足）{q['exp']}"
        s.last_feedback = feedback

        # 10問区切りでブロック集計
        if s.answered % 10 == 0 or s.answered == TOTAL:
            block = chunk_number(s.answered)
            start_i = (block - 1) * 10
            end_i = min(block * 10, TOTAL)
            # 集計は差分ではなく、その区間での正答数を算出
            # ここでは簡略化：区切りのたびに「ここまでの正解数 - 直前ブロックまでの合計」で求める
            prev_sum = sum(s.chunk_scores.values())
            s.chunk_scores[block] = s.correct - prev_sum

        # 次のインデックスへ
        s.idx += 1

        # 返答
        if s.answered >= TOTAL:
            # 最終結果
            rate = s.correct / TOTAL * 100.0
            end_msg = (
                f"{feedback}\n\n"
                f"🏁 全問終了！\n"
                f"最終成績：{s.correct}/{TOTAL}（{rate:.1f}%）\n"
                f"リッチメニューの「成績確認」でブロック別の内訳も確認できます。"
            )
            send_text(user_id, end_msg)
        else:
            # 10問ごとの速報
            if s.answered % 10 == 0:
                block = chunk_number(s.answered)
                bsc = s.chunk_scores.get(block, 0)
                summary = f"📝 {((block-1)*10+1):02d}〜{(block*10):02d}問の成績：{bsc}/10"
                send_text(user_id, f"{feedback}\n\n{summary}\n\n次の問題はリッチメニューからどうぞ。")
            else:
                send_text(user_id, f"{feedback}\n\n次の問題はリッチメニューの『次の問題』をタップ。")
        return

    # それ以外の入力
    send_text(
        user_id,
        "入力を理解できませんでした。\n"
        "・「クイズ」または「開始」でスタート\n"
        "・答えは 1 / 2 / 3 / 4 で送信\n"
        "・『次の問題』『成績確認』は下のリッチメニューから\n"
        "・「ステータス」「リセット」「ヘルプ」も使えます。"
    )
