# -*- coding: utf-8 -*-
# 乙4クイズ LINE Bot（Flask版・50問フル実装）
# - /health あり
# - 出題は4択ボタン（Template/Buttons）
# - 回答後は「次の問題」「リセット」「ヘルプ」
# - 25問/50問で総括メッセージ
# - 簡易メモリ（サーバ再起動で消えます）

import os
from flask import Flask, request, abort, jsonify

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    TemplateSendMessage, ButtonsTemplate, PostbackAction,
    PostbackEvent
)

# ===== LINE 環境変数 =====
CHANNEL_TOKEN  = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
if not CHANNEL_TOKEN or not CHANNEL_SECRET:
    raise RuntimeError("環境変数 LINE_CHANNEL_ACCESS_TOKEN / LINE_CHANNEL_SECRET を設定してください。")

line_bot_api = LineBotApi(CHANNEL_TOKEN)
handler      = WebhookHandler(CHANNEL_SECRET)

# ===== Flask =====
app = Flask(__name__)

@app.get("/health")
def health():
    return jsonify({"status": "ok"})

@app.post("/callback")
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400, "Invalid signature")
    return "OK"

# ===== ヘルプ =====
HELP_TEXT = (
    "📘 使い方\n"
    "・「開始」→ 出題スタート\n"
    "・4択ボタン（①〜④）で回答\n"
    "・「次の問題」で続行 / 「成績確認」で途中成績\n"
    "・「リセット」で最初から\n"
    "・25問/50問で総括が出ます"
)

# ===== 50問フル実装（法令・物理化学・性状消火）=====
# 形式: {"q": str, "choices": [str×4], "answer": 0-3, "exp": str}
QUESTIONS = [
    # --- 法令 ---
    {"q":"第1石油類（非水溶性）の指定数量は？", "choices":["100L","200L","400L","1000L"], "answer":0, "exp":"第1石油類（非水溶性/水溶性）は100L。"},
    {"q":"第2石油類（非水溶性）の指定数量は？", "choices":["500L","1000L","2000L","4000L"], "answer":2, "exp":"第2石油類（非水溶性）は2000L。"},
    {"q":"第2石油類（水溶性）の指定数量は？", "choices":["1000L","2000L","3000L","4000L"], "answer":1, "exp":"第2石油類（水溶性）は2000L。"},
    {"q":"アルコール類の指定数量は？", "choices":["100L","200L","400L","600L"], "answer":2, "exp":"アルコール類の指定数量は400L。"},
    {"q":"第3石油類の指定数量は？", "choices":["1000L","2000L","3000L","4000L"], "answer":3, "exp":"第3石油類は4000L。"},
    {"q":"第4石油類の指定数量は？", "choices":["1000L","2000L","4000L","6000L"], "answer":3, "exp":"第4石油類は6000L。"},
    {"q":"乙4で取り扱う類は？", "choices":["第1類","第2類","第3類","第4類"], "answer":3, "exp":"乙4は第4類（引火性液体）。"},
    {"q":"危険物規制の根拠法は？", "choices":["労働基準法","消防法","建築基準法","安衛法"], "answer":1, "exp":"危険物は消防法に基づく規制。"},
    {"q":"指定数量以上の貯蔵・取扱いに必要なのは？", "choices":["届出不要","消防法の許可等","警察許可","厚労省許可"], "answer":1, "exp":"所轄消防署の許可等が必要。"},
    {"q":"少量危険物に該当するのは？", "choices":["指定数量未満でも全部規制なし","指定数量の1/5以上などで基準あり","指定数量超と同じ","税務署の許可"], "answer":1, "exp":"少量危険物には技術上の基準あり。"},
    {"q":"危険物施設の標識で正しいのは？", "choices":["白地赤枠赤字","黄地黒字","青地白字","緑地白字"], "answer":0, "exp":"『火気厳禁』など白地赤枠赤字。"},
    {"q":"掲示義務がないものは？", "choices":["類別・品名","禁止事項","取扱者名簿","避難経路図"], "answer":3, "exp":"避難経路図は法令の掲示義務対象外。"},
    {"q":"危険物運搬時の標識表示で必要なのは？", "choices":["車両前後などに標識","屋根旗","運転席のみ表示","不要"], "answer":0, "exp":"積載標識などが必要（条件により）。"},
    {"q":"保安距離の目的は？", "choices":["装飾","延焼・被害拡大防止","換気停止","荷重支持"], "answer":1, "exp":"周辺への被害拡大を抑える。"},
    {"q":"受入時に最初に行うべきことは？", "choices":["マンホール開放","接地（アース）","火気設置","圧送スタート"], "answer":1, "exp":"静電気着火防止のためアース先行。"},
    # --- 物理化学 ---
    {"q":"引火点とは？", "choices":["自然発火温度","火源で着火する最低温度","沸点","凝固点"], "answer":1, "exp":"可燃蒸気が火源で着火する最低温度。"},
    {"q":"発火点とは？", "choices":["火源なしで燃え始める温度","引火点より低い温度","水の沸点","蒸気圧"], "answer":0, "exp":"外火なしで自己着火する温度。"},
    {"q":"蒸気密度（比重）が1より大きい可燃蒸気は？", "choices":["高所に滞留","低所に滞留","中層に滞留","影響なし"], "answer":1, "exp":"空気より重い→低所に滞留。"},
    {"q":"蒸気圧が高いほど？", "choices":["揮発しにくい","揮発しやすい","密度が上がる","引火点が上がる"], "answer":1, "exp":"揮発しやすく危険性が増す。"},
    {"q":"可燃範囲が広いほど？", "choices":["危険性低い","危険性高い","変わらない","燃えない"], "answer":1, "exp":"着火しやすく危険性が高い。"},
    {"q":"爆発下限界より濃度が低い混合気は？", "choices":["薄すぎて燃えない","濃すぎて燃えない","必ず爆発","自然発火"], "answer":0, "exp":"燃料不足で燃えない。"},
    {"q":"静電気対策として適切なのは？", "choices":["乾燥維持","接地・等電位化","樹脂容器同士で移送","換気停止"], "answer":1, "exp":"アースや導電化で放電路を確保。"},
    {"q":"比熱が大きい物体の特徴は？", "choices":["温度が上がりやすい","温度が上がりにくい","発火しやすい","蒸発しやすい"], "answer":1, "exp":"同じ熱量で温度変化が小さい。"},
    {"q":"ガソリンの特徴で正しいのは？", "choices":["沸点が高い","引火点が非常に低い","水に溶けやすい","蒸気は空気より軽いことが多い"], "answer":1, "exp":"引火点が非常に低く危険。"},
    {"q":"芳香族炭化水素の一般的性質は？", "choices":["水に溶けやすい","水に溶けにくい","強酸性","強塩基性"], "answer":1, "exp":"疎水性で水と混ざりにくい。"},
    {"q":"換気の主目的は？", "choices":["湿度低下","蒸気濃度低減","温度差低減","圧力損失低減"], "answer":1, "exp":"可燃蒸気濃度を下げる。"},
    {"q":"アセトンはどの分類？", "choices":["第1石油類（非水溶性）","第1石油類（水溶性）","第2石油類","アルコール類"], "answer":1, "exp":"水と任意比で混和→第1石油類（水溶性）。"},
    {"q":"トルエンはどの分類？", "choices":["第1石油類（非水）","第1石油類（水）","第2石油類","第3石油類"], "answer":0, "exp":"非水溶性の第1石油類。"},
    {"q":"軽油はどの分類？", "choices":["第1石油類","第2石油類","第3石油類","第4石油類"], "answer":1, "exp":"軽油は第2石油類（非水溶性）。"},
    # --- 性状・消火 ---
    {"q":"油火災に水を直接かけると？", "choices":["安全に消える","油が飛散し危険","必ず爆発","固化する"], "answer":1, "exp":"飛散・延焼の危険が高い。"},
    {"q":"アルコール火災に有効な消火剤は？", "choices":["普通泡のみ","耐アルコール泡や粉末","水のみ","乾燥砂のみ"], "answer":1, "exp":"ATC泡・粉末等が有効。"},
    {"q":"二酸化炭素消火の主作用は？", "choices":["冷却","窒息","希釈","乳化"], "answer":1, "exp":"CO2は酸素を置換して窒息効果。"},
    {"q":"粉末ABC消火薬剤の主作用は？", "choices":["冷却","連鎖反応抑制","希釈","乳化"], "answer":1, "exp":"ラジカル反応を抑制。"},
    {"q":"電気火災でまず行うことは？", "choices":["送風","給電遮断","水噴霧","泡散布"], "answer":1, "exp":"感電防止のため遮断が先。"},
    {"q":"金属ナトリウム火災で適切なのは？", "choices":["水","泡","乾燥砂・金属用粉末","CO2"], "answer":2, "exp":"水・泡は禁忌。乾燥砂等を使用。"},
    {"q":"流出油火災の基本戦術は？", "choices":["放水で押し流す","フォームで被覆","空気送り込み","撹拌"], "answer":1, "exp":"泡で表面を覆い窒息・遮断。"},
    {"q":"ATC泡（耐アルコール泡）の用途は？", "choices":["非水溶性のみ","水溶性溶剤にも有効","気体火災専用","金属火災専用"], "answer":1, "exp":"水溶性にも対応。"},
    {"q":"CO2消火の弱点は？", "choices":["通電部位では使えない","屋外で風に流されやすい","腐食性が強い","泡を分解する"], "answer":1, "exp":"屋外では吹き飛ばされやすい。"},
    {"q":"潤滑油はどの分類？", "choices":["第1石油類","第2石油類","第3石油類","第4石油類"], "answer":2, "exp":"潤滑油は第3石油類。"},
    {"q":"ベンゼンの引火点の目安は？", "choices":["約-20℃","約0℃","約30℃","約80℃"], "answer":0, "exp":"非常に低い引火点を持つ。"},
    {"q":"受入作業時の服装で不適切なのは？", "choices":["帯電防止服","静電靴","化繊フリース","綿作業着"], "answer":2, "exp":"化繊フリースは帯電しやすい。"},
    {"q":"移送で避けるべきは？", "choices":["金属配管で接地","樹脂容器同士の手持ち移送","導電性ホース","液面下注入"], "answer":1, "exp":"樹脂容器間移送は静電気危険。"},
    {"q":"ブリーザー（呼吸装置）の目的は？", "choices":["消火","圧力変動調整","蒸気回収","着火"], "answer":1, "exp":"タンク内圧の変動を調整。"},
    {"q":"タンク火災で重要なのは？", "choices":["上部から送風","フォームで被覆","空気送入","撹拌"], "answer":1, "exp":"泡で液面を覆う。"},
    {"q":"指定数量以上の取扱所で必須の有資格者は？", "choices":["危険物取扱者","毒物劇物取扱者","電気主任技術者","ボイラー技士"], "answer":0, "exp":"危険物取扱者が必要。"},
    {"q":"水溶性第1石油類はどれ？", "choices":["アセトン","トルエン","キシレン","ベンゼン"], "answer":0, "exp":"アセトンは水と任意比で混和。"},
    {"q":"ガソリンの主成分は？", "choices":["アルコール","炭化水素","アルデヒド","ケトン"], "answer":1, "exp":"炭化水素が主体。"},
    {"q":"指定数量未満でも必要なのは？", "choices":["一切不要","一部基準の遵守","必ず許可","税務届出"], "answer":1, "exp":"少量危険物等の基準がある。"},
    {"q":"可燃蒸気は一般に空気より？", "choices":["軽い","同じ","重い","変わらない"], "answer":2, "exp":"多くは空気より重く低所に滞留。"},
    {"q":"油水分離マットの目的は？", "choices":["吸音","油吸着","消火","発熱"], "answer":1, "exp":"漏えい対策に用いる吸着材。"},
    {"q":"避雷設備の目的は？", "choices":["騒音低減","雷電流を大地に逃がす","冷却","消火"], "answer":1, "exp":"雷や静電気の着火リスク低減。"},
    {"q":"運搬積載量を定める法は？", "choices":["消防法","道路交通法","安衛法","建築基準法"], "answer":1, "exp":"道路交通法などで規定。"},
    {"q":"服装で適切なのは？", "choices":["帯電防止服＋静電靴","化繊フリース","サンダル","ウール100%"], "answer":0, "exp":"帯電防止対策の基本。"},
    {"q":"泡消火の主作用は？", "choices":["冷却","窒息・遮断","希釈","連鎖反応抑制"], "answer":1, "exp":"表面を覆い空気と遮断。"},
    {"q":"二酸化炭素消火が苦手な場面は？", "choices":["屋内","密閉空間","屋外の強風下","電気火災"], "answer":2, "exp":"風で飛散しやすい。"},
]

TOTAL = len(QUESTIONS)  # 50

# ===== ユーザー状態 =====
# user_id -> {"qid": int, "correct": int, "answered": int}
STATE = {}

def reset_state(uid: str):
    STATE[uid] = {"qid": 0, "correct": 0, "answered": 0}

def buttons_for_question(q_index: int) -> TemplateSendMessage:
    q = QUESTIONS[q_index]
    actions = [
        PostbackAction(label=f"① {q['choices'][0]}", data=f"ans:{q_index}:0"),
        PostbackAction(label=f"② {q['choices'][1]}", data=f"ans:{q_index}:1"),
        PostbackAction(label=f"③ {q['choices'][2]}", data=f"ans:{q_index}:2"),
        PostbackAction(label=f"④ {q['choices'][3]}", data=f"ans:{q_index}:3"),
    ]
    tmpl = ButtonsTemplate(
        title=f"Q{q_index+1}/{TOTAL}",
        text=q["q"],
        actions=actions
    )
    return TemplateSendMessage(alt_text="問題", template=tmpl)

def buttons_after_answer() -> TemplateSendMessage:
    return TemplateSendMessage(
        alt_text="操作",
        template=ButtonsTemplate(
            title="次の操作",
            text="選んでください",
            actions=[
                PostbackAction(label="▶ 次の問題", data="next"),
                PostbackAction(label="🔄 リセット", data="reset"),
                PostbackAction(label="❓ ヘルプ", data="help"),
            ]
        )
    )

def summary_text(uid: str, title: str) -> str:
    st = STATE[uid]
    a, c = st["answered"], st["correct"]
    rate = 0 if a == 0 else round(100*c/a, 1)
    return f"📊 {title}\n解答数: {a}/{TOTAL}\n正解: {c}\n正答率: {rate}%"

# ===== Handlers =====
@handler.add(MessageEvent, message=TextMessage)
def on_text(event: MessageEvent):
    uid = event.source.user_id
    text = (event.message.text or "").strip()

    if uid not in STATE:
        reset_state(uid)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"{HELP_TEXT}\n\nまずは「開始」と送ってください。")
        )
        return

    if text in {"ヘルプ", "help", "使い方", "？"}:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=HELP_TEXT))
        return

    if text in {"リセット", "reset"}:
        reset_state(uid)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="♻️ リセットしました。「開始」で再開できます。")
        )
        return

    if text in {"成績確認", "ステータス"}:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=summary_text(uid, "現在の成績")))
        return

    if text in {"開始", "問題", "クイズ", "次の問題", "start"}:
        st = STATE[uid]
        qid = st["qid"]
        if qid >= TOTAL:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="✅ 全50問終了！「リセット」で再挑戦できます。")
            )
            return
        line_bot_api.reply_message(event.reply_token, buttons_for_question(qid))
        return

    # フォールバック
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="『開始』『次の問題』『成績確認』『リセット』『ヘルプ』を使ってください。")
    )

@handler.add(PostbackEvent)
def on_postback(event: PostbackEvent):
    uid = event.source.user_id
    data = event.postback.data

    if uid not in STATE:
        reset_state(uid)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="まずは「開始」と送ってください。"))
        return

    st = STATE[uid]

    # 回答
    if data.startswith("ans:"):
        _, qid_str, ans_str = data.split(":")
        qid = int(qid_str); ans = int(ans_str)
        q = QUESTIONS[qid]

        st["answered"] += 1
        correct = (ans == q["answer"])
        if correct:
            st["correct"] += 1

        result = "⭕ 正解！" if correct else f"❌ 不正解… 正解は『{q['choices'][q['answer']]}』"
        msg = f"{result}\n（補足）{q['exp']}"

        # 25問/50問で総括
        extra = ""
        if st["answered"] in (25, 50):
            extra = "\n\n" + summary_text(uid, f"{st['answered']}問総括")

        # 回答後の操作ボタン
        line_bot_api.reply_message(event.reply_token, [
            TextSendMessage(text=msg + extra),
            buttons_after_answer()
        ])
        return

    # 次の問題
    if data == "next":
        st["qid"] += 1
        if st["qid"] >= TOTAL:
            # 終了・最終サマリ
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=summary_text(uid, "最終成績") + "\n✅ 全50問終了！「リセット」で再挑戦できます。")
            )
            return
        line_bot_api.reply_message(event.reply_token, buttons_for_question(st["qid"]))
        return

    # リセット
    if data == "reset":
        reset_state(uid)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🔄 リセットしました。「開始」で再開できます。"))
        return

    # ヘルプ
    if data == "help":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=HELP_TEXT))
        return

# ローカル起動用（Renderでは無視される）
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
