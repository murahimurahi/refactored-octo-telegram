import os
import random
from flask import Flask, request, abort, jsonify

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)

# ====== 環境変数（Render/Heroku の環境変数に設定）======
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
CHANNEL_TOKEN  = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
if not CHANNEL_SECRET or not CHANNEL_TOKEN:
    raise RuntimeError("環境変数 LINE_CHANNEL_SECRET / LINE_CHANNEL_ACCESS_TOKEN を設定してください。")

line_bot_api = LineBotApi(CHANNEL_TOKEN)
handler      = WebhookHandler(CHANNEL_SECRET)

# ====== Flask ======
app = Flask(__name__)

# /health 監視用
@app.get("/health")
def health():
    return jsonify({"status": "ok"})

# ====== ヘルプ本文 ======
HELP_TEXT = (
    "📘 使い方\n"
    "・「開始」「問題」「クイズ」で出題スタート\n"
    "・4択は下の《①②③④》ボタンで回答\n"
    "・「次の問題」でもう1問\n"
    "・「成績確認」で現在の正答率\n"
    "・「リセット」で成績と出題履歴を初期化\n"
    "（※学習用の簡易ボットです。過去問50問をランダム出題。"
    "のちほど言い回しや分野バランス（法令/物化/性消）も調整予定）"
)

# ====== ユーザー別ステート（メモリ保持）======
# ※サーバ再起動でリセットされます。必要ならDB化してください。
STATE = {}  # uid -> {"answered":int,"correct":int,"asked_ids":set(),"last_q_id":int}

# ====== クイックリプライ ======
def qr_answer_buttons():
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="①", text="1")),
        QuickReplyButton(action=MessageAction(label="②", text="2")),
        QuickReplyButton(action=MessageAction(label="③", text="3")),
        QuickReplyButton(action=MessageAction(label="④", text="4")),
    ])

def qr_reset_help():
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="🔄 リセット", text="リセット")),
        QuickReplyButton(action=MessageAction(label="❓ ヘルプ", text="ヘルプ")),
    ])

def qr_next_or_menu():
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="▶ 次の問題", text="次の問題")),
        QuickReplyButton(action=MessageAction(label="📊 成績確認", text="成績確認")),
        QuickReplyButton(action=MessageAction(label="🔄 リセット", text="リセット")),
        QuickReplyButton(action=MessageAction(label="❓ ヘルプ", text="ヘルプ")),
    ])

# ====== 問題データ（50問）======
# ・ans は 1〜4
# ・exp は簡潔な補足（調整OK）
QUESTIONS = [
    # --- 法令系 ---
    {"id": 1, "q": "第1石油類の指定数量は？", "choices": ["100L", "200L", "400L", "1000L"], "ans":1, "exp":"第1石油類（非水溶性/水溶性）は 100L"},
    {"id": 2, "q": "第2石油類（水溶性）の指定数量は？", "choices": ["1000L", "2000L", "4000L", "6000L"], "ans":2, "exp":"第2石油類（水溶性）は 2000L"},
    {"id": 3, "q": "指定数量以上の貯蔵・取扱いには原則どの許可が必要？", "choices": ["届出不要", "消防法の許可等", "所轄警察のみ", "厚労省のみ"], "ans":2, "exp":"消防機関の許可等が必要"},
    {"id": 4, "q": "危険物取扱者乙4の取扱対象は？", "choices": ["第1類", "第2類", "第3類", "第4類"], "ans":4, "exp":"乙4は第4類（引火性液体）"},
    {"id": 5, "q": "指定数量の倍数が10以上の場所の標識は？", "choices": ["黄地黒枠", "白地赤枠", "赤地白字", "黒地黄字"], "ans":2, "exp":"危険物の標識は白地に赤枠赤字"},
    {"id": 6, "q": "指定数量未満でも必要なものは？", "choices": ["許可", "屋内貯蔵所設置義務", "少量危険物の基準遵守", "罰則なし"], "ans":3, "exp":"少量危険物の技術上基準あり"},
    {"id": 7, "q": "灯油（第4類第2石油類）の指定数量は？", "choices": ["100L", "200L", "1000L", "2000L"], "ans":4, "exp":"第2石油類（非水溶性）2000L"},
    {"id": 8, "q": "危険物施設の保安監督者が行うものは？", "choices": ["設備の点検", "通貨換算", "労基署申請", "監査役選任"], "ans":1, "exp":"保安業務の中心"},
    {"id": 9, "q": "引火点が最も低いのは？", "choices": ["ガソリン", "軽油", "灯油", "A重油"], "ans":1, "exp":"ガソリンは-40℃前後で非常に低い"},
    {"id":10, "q": "危険物の類別で『自己反応性』は？", "choices": ["第1類", "第3類", "第5類", "第6類"], "ans":3, "exp":"第5類：自己反応性物質"},
    # --- 物理化学 ---
    {"id":11, "q": "可燃性蒸気が空気と混合し燃焼し得る濃度範囲を何という？", "choices": ["発火点", "爆発限界", "沸点", "蒸気圧"], "ans":2, "exp":"下限～上限の範囲"},
    {"id":12, "q": "沸点が最も低いのは？", "choices": ["ガソリン", "灯油", "軽油", "A重油"], "ans":1, "exp":"沸点が低い＝揮発しやすい"},
    {"id":13, "q": "蒸気比重が1より大きい蒸気の性質は？", "choices": ["上に溜まる", "下に溜まる", "どこにも溜まらない", "発光する"], "ans":2, "exp":"空気より重いと低所に滞留"},
    {"id":14, "q": "蒸気圧が高いほど？", "choices": ["気化しにくい", "気化しやすい", "密度が上がる", "引火点上がる"], "ans":2, "exp":"蒸発しやすい→危険性上昇"},
    {"id":15, "q": "発火点とは？", "choices": ["自然発火する温度", "引火点より低い", "水の沸点", "凝固点"], "ans":1, "exp":"外火なしで発火する温度"},
    {"id":16, "q": "引火点に影響が大きいのは？", "choices": ["分子量", "蒸気圧", "色", "音"], "ans":2, "exp":"蒸気圧が高いほど引火しやすい"},
    {"id":17, "q": "静電気対策で正しいのは？", "choices": ["湿度を上げる", "換気を止める", "接地を外す", "合成繊維を勧める"], "ans":1, "exp":"加湿と接地で帯電防止"},
    {"id":18, "q": "爆発限界の下限より下の混合気は？", "choices": ["濃すぎて燃えない", "薄すぎて燃えない", "必ず爆発", "自然発火"], "ans":2, "exp":"可燃成分が不足"},
    {"id":19, "q": "比熱の大きい物体の特徴は？", "choices": ["温度が変わりにくい", "すぐ熱くなる", "発火しやすい", "蒸発しやすい"], "ans":1, "exp":"熱容量が大きい"},
    {"id":20, "q": "ガソリンの主成分は？", "choices": ["アルコール", "炭化水素", "アルデヒド", "ケトン"], "ans":2, "exp":"炭化水素（C,H）主体"},
    # --- 性質・消火 ---
    {"id":21, "q": "水溶性の第1石油類はどれ？", "choices": ["アセトン", "トルエン", "キシレン", "ベンゼン"], "ans":1, "exp":"アセトンは水と任意率で混和"},
    {"id":22, "q": "アルコール火災に有効な消火剤は？", "choices": ["水のみ", "泡（耐アルコール性）", "金属粉", "炭酸ガスのみ"], "ans":2, "exp":"耐アルコール泡を用いる"},
    {"id":23, "q": "電気火災でまず行うことは？", "choices": ["給電遮断", "水をかける", "紙で覆う", "酸素供給"], "ans":1, "exp":"感電防止のため遮断が先"},
    {"id":24, "q": "油火災に水を直接かけると？", "choices": ["素早く消える", "拡散して危険", "発光する", "固化する"], "ans":2, "exp":"飛散して延焼・フラッシュ"},
    {"id":25, "q": "泡消火の主たる消火作用は？", "choices": ["冷却", "窒息・抑制", "抑制のみ", "希釈"], "ans":2, "exp":"表面を覆い空気遮断＋蒸発抑制"},
    {"id":26, "q": "二酸化炭素消火の弱点は？", "choices": ["通電部位不可", "冷却が強すぎる", "屋外で吹き飛ばされやすい", "腐食性が強い"], "ans":3, "exp":"風で飛散しやすい"},
    {"id":27, "q": "粉末ABC消火薬剤の作用は？", "choices": ["冷却", "酸素希釈", "連鎖反応抑制", "吸着"], "ans":3, "exp":"ラジカル反応を止める"},
    {"id":28, "q": "水系消火剤の主作用は？", "choices": ["窒息", "希釈", "冷却", "抑制"], "ans":3, "exp":"水は蒸発潜熱で冷却"},
    {"id":29, "q": "タンク火災の消火戦術で重要なのは？", "choices": ["頂部冷却のみ", "フォームで被覆", "空気送入", "バルブ全開"], "ans":2, "exp":"泡で表面を覆う"},
    {"id":30, "q": "可燃性液体の漏えい時、まず行うのは？", "choices": ["点火源除去・立入禁止", "送風", "水で洗い流す", "すべて焼却"], "ans":1, "exp":"二次災害防止が最優先"},
    # --- 以降も同様に50問まで ---
    {"id":31, "q": "アセトンの類別は？", "choices": ["第1石油類", "第2石油類", "第3石油類", "第4石油類"], "ans":1, "exp":"水溶性の第1石油類"},
    {"id":32, "q": "軽油の類別は？", "choices": ["第1", "第2", "第3", "第4"], "ans":2, "exp":"軽油は第2石油類（非水溶性）"},
    {"id":33, "q": "キシレンの類別は？", "choices": ["第1", "第2", "第3", "第4"], "ans":2, "exp":"芳香族の第2石油類"},
    {"id":34, "q": "エタノールの類別は？", "choices": ["第1（水溶性）", "第2（水溶性）", "第3", "第4"], "ans":1, "exp":"アルコールは第1（水溶性）"},
    {"id":35, "q": "重油の類別は？", "choices": ["第2", "第3", "第4", "指定外"], "ans":2, "exp":"重油は第3石油類"},
    {"id":36, "q": "ベンゼンの引火点は概ね？", "choices": ["-20℃", "0℃前後", "30℃", "100℃"], "ans":1, "exp":"非常に低い引火点"},
    {"id":37, "q": "芳香族炭化水素の一般的特徴は？", "choices": ["水に溶けやすい", "水に溶けにくい", "強酸性", "強塩基性"], "ans":2, "exp":"疎水性で比重は水より小さいことが多い"},
    {"id":38, "q": "密閉空間でのガソリン作業で必須は？", "choices": ["送風機で換気", "加湿", "暖房", "加圧"], "ans":1, "exp":"換気で濃度低減"},
    {"id":39, "q": "泡原液の保存で大切なのは？", "choices": ["直射日光", "密栓と清潔", "加熱", "撹拌し続ける"], "ans":2, "exp":"劣化・汚染防止"},
    {"id":40, "q": "危険物施設の避雷設備の目的は？", "choices": ["騒音低減", "雷撃電流を大地へ逃がす", "冷却", "消火"], "ans":2, "exp":"静電気・雷の着火防止"},
    {"id":41, "q": "指定数量の倍数は何に用いる？", "choices": ["危険等級", "標識の色", "保安距離等の判定", "容器形状"], "ans":3, "exp":"技術上の基準の適用範囲判定"},
    {"id":42, "q": "ガソリン火災の第一選択は？", "choices": ["放水", "粉末/泡", "二酸化炭素", "水噴霧"], "ans":2, "exp":"泡か粉末が基本"},
    {"id":43, "q": "水溶性溶剤の火災で通常泡を使うと？", "choices": ["よく効く", "分解され効かない", "金属化する", "結晶化する"], "ans":2, "exp":"耐アルコール泡を使用"},
    {"id":44, "q": "危険物の移送で摩擦帯電を抑えるには？", "choices": ["非導電ホース", "導電性ホースと接地", "断熱材", "保温"], "ans":2, "exp":"導電化＋アースで放電路を確保"},
    {"id":45, "q": "消防計画に含むべき事項は？", "choices": ["販売価格", "訓練計画", "株主構成", "賃金"], "ans":2, "exp":"防火管理の骨子"},
    {"id":46, "q": "危険物屋内貯蔵所の通路幅は概ね？", "choices": ["0.3m", "0.6m", "1.0m", "2.0m"], "ans":3, "exp":"安全な避難・搬出のため"},
    {"id":47, "q": "引火性液体の着火源でないものは？", "choices": ["静電気", "裸火", "衝撃音", "高温表面"], "ans":3, "exp":"音自体は着火源ではない"},
    {"id":48, "q": "油水分離マットの目的は？", "choices": ["吸音", "油吸着", "消火", "発熱"], "ans":2, "exp":"漏えい対策で使用"},
    {"id":49, "q": "危険物の運搬で必要な表示は？", "choices": ["車両前後に標識", "屋根上フラッグ", "運転席のみ", "不要"], "ans":1, "exp":"積載表示・標識が必要（規模で差）"},
    {"id":50, "q": "50問終了時に推奨される操作は？", "choices": ["送風", "リセットして再挑戦", "消火器点検", "通報"], "ans":2, "exp":"成績確認→リセットで周回学習へ"},
]

# ====== 出題ロジック ======
def next_question(uid: str):
    st = STATE[uid]
    # 全問済なら終了案内
    if len(st["asked_ids"]) >= len(QUESTIONS):
        msg = "🎉 全50問終了！\n📊「成績確認」で結果を確認 → 「リセット」で再挑戦できます。"
        return TextSendMessage(text=msg, quick_reply=qr_reset_help())

    # 未出題からランダム
    pool = [q for q in QUESTIONS if q["id"] not in st["asked_ids"]]
    q = random.choice(pool)
    st["last_q_id"] = q["id"]

    body = [f"Q{st['answered']+1}/50: {q['q']}"]
    for i, ch in enumerate(q["choices"], start=1):
        body.append(f"{i} {ch}")
    txt = "\n".join(body)
    return TextSendMessage(text=txt, quick_reply=qr_answer_buttons())

def evaluate(uid: str, choice_text: str):
    st = STATE[uid]
    # 文字→番号（1～4）へ
    mapping = {"１":"1","２":"2","３":"3","４":"4","①":"1","②":"2","③":"3","④":"4"}
    ans_txt = mapping.get(choice_text.strip(), choice_text.strip())
    if ans_txt not in {"1","2","3","4"} or st.get("last_q_id") is None:
        return TextSendMessage(text="①〜④で回答してください。", quick_reply=qr_answer_buttons())

    qid = st["last_q_id"]
    q = next(item for item in QUESTIONS if item["id"] == qid)
    st["answered"] += 1
    st["asked_ids"].add(qid)

    correct = int(ans_txt) == int(q["ans"])
    if correct:
        st["correct"] += 1
        feedback = f"⭕ 正解！\n（補足）{q['exp']}"
    else:
        feedback = f"❌ 不正解…\n正解は {q['ans']}：{q['choices'][q['ans']-1]}\n（補足）{q['exp']}"

    # 指定：回答後は《リセット/ヘルプ》のみ
    return TextSendMessage(text=feedback, quick_reply=qr_reset_help())

def make_status(uid: str):
    st = STATE[uid]
    a = st["answered"]
    c = st["correct"]
    rate = f"{(c/a*100):.1f}%" if a else "0%"
    msg = f"📊 成績\n解答数: {a}/50\n正解: {c}\n正答率: {rate}\n『次の問題』で続行できます。"
    return TextSendMessage(text=msg, quick_reply=qr_next_or_menu())

def reset_state(uid: str):
    STATE[uid] = {"answered":0,"correct":0,"asked_ids":set(),"last_q_id":None}

# ====== LINE Webhook ======
@app.post("/callback")
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body      = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def on_message(event: MessageEvent):
    uid  = event.source.user_id
    text = (event.message.text or "").strip()

    # 初回ユーザーはステート作ってヘルプを返す（指定どおり）
    if uid not in STATE:
        reset_state(uid)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=HELP_TEXT, quick_reply=qr_next_or_menu())
        )
        return

    # コマンド系
    if text in {"ヘルプ","help","使い方"}:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=HELP_TEXT, quick_reply=qr_next_or_menu()))
        return
    if text in {"リセット","reset"}:
        reset_state(uid)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🧹 セッションをリセットしました。\n『次の問題』で再開できます。", quick_reply=qr_next_or_menu()))
        return
    if text in {"成績確認","ステータス","スコア","成績"}:
        line_bot_api.reply_message(event.reply_token, make_status(uid))
        return
    if text in {"次の問題","開始","問題","クイズ","start","スタート"}:
        line_bot_api.reply_message(event.reply_token, next_question(uid))
        return

    # 回答（1〜4/①〜④）
    if text in {"1","2","3","4","１","２","３","４","①","②","③","④"}:
        line_bot_api.reply_message(event.reply_token, evaluate(uid, text))
        return

    # フォールバック
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="『次の問題』『成績確認』『リセット』『ヘルプ』を使ってね。", quick_reply=qr_next_or_menu())
    )

# ====== ローカル起動用 ======
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
