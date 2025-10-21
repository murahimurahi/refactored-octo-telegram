# -*- coding: utf-8 -*-
import os
from flask import Flask, request, abort, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)

# -----------------------------
# Flask
# -----------------------------
app = Flask(__name__)

@app.get("/")
def root():
    return jsonify({"ok": True})

@app.get("/health")
def health():
    return jsonify({"status": "ok"})

# -----------------------------
# LINE keys（環境変数に入れてね）
# -----------------------------
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "YOUR_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "YOUR_CHANNEL_SECRET")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# -----------------------------
# 過去問 50問（法令/物理化学/性質消火をバランス投入）
# ans は 1〜4、exp は解説
# -----------------------------
Q = [
# ---- 法令（1〜18） ----
{"q":"第4類危険物の本質は？","choices":["酸化性液体","引火性液体","可燃性液体","腐食性液体"],"ans":2,"exp":"乙4は“引火性液体”を扱う免状。"},
{"q":"危険物取扱者免状を交付するのは？","choices":["消防庁長官","市町村長","都道府県知事","消防署長"],"ans":3,"exp":"免状交付は都道府県知事。"},
{"q":"製造所等の許可権者は？","choices":["消防庁長官","都道府県知事","市町村長","消防署長"],"ans":2,"exp":"許可は基本都道府県知事（条例で政令市等へ委任あり）。"},
{"q":"少量危険物の上限（第4類）は？","choices":["指定数量の十分の一未満","指定数量の五分の一未満","指定数量未満","指定数量の二分の一未満"],"ans":1,"exp":"“少量危険物”は指定数量の1/10未満。"},
{"q":"少量危険物の“倍数”の数え方は？","choices":["切り上げ","切り捨て","四捨五入","端数は0扱い"],"ans":1,"exp":"少量倍数は切り上げ。"},
{"q":"貯蔵・取扱いの“届出先”は？","choices":["都道府県知事","消防署長等","総務大臣","市町村長"],"ans":2,"exp":"届出や規制の実務は消防機関（消防長/消防署長等）。"},
{"q":"危険物の規制に関する政令は？","choices":["消防法施行令","労働安全衛生法施行令","毒劇法施行令","危険物運搬令"],"ans":1,"exp":"消防法施行令がベース。"},
{"q":"屋内貯蔵所の所要床面積区画に関係するのは？","choices":["防火壁","防液堤","防油堤","防火戸"],"ans":2,"exp":"液体なので“防液堤”（防油堤同義）。"},
{"q":"仮貯蔵・仮取扱いの許可権者は？","choices":["消防庁長官","消防署長等","都道府県知事","市町村長"],"ans":2,"exp":"実務は消防署長等。"},
{"q":"危険物施設保安員の選任が不要なのは？","choices":["製造所","屋外タンク貯蔵所","給油取扱所","移送取扱所"],"ans":3,"exp":"給油取扱所は“取扱所”で保安員不要。"},
{"q":"定期点検を要するのは？","choices":["仮貯蔵のみ","少量危険物のみ","指定数量以上の製造所等","全て不要"],"ans":3,"exp":"指定数量以上の製造所等は保安検査等が必要。"},
{"q":"危険物取扱者が“立会い”を要する作業は？","choices":["帳票作成","清掃","注油・抜油等の危険物の移動","見回り"],"ans":3,"exp":"危険物の移動・移送は立会い対象。"},
{"q":"危険物の分類表示で第4類の色は？","choices":["赤","黄","青","緑"],"ans":1,"exp":"第4類は“赤”。"},
{"q":"異種混合で特に禁忌は？","choices":["水と混合","酸化剤と混合","空気と混合","窒素と混合"],"ans":2,"exp":"第4類は酸化剤と混合厳禁（爆発・激発火）。"},
{"q":"指定数量1000Lの品目は？","choices":["重油","ガソリン","灯油","アルコール類"],"ans":1,"exp":"重油は1000L、灯油・軽油も1000L、ガソリンは200L。"},
{"q":"給油取扱所の火気使用は？","choices":["指定場所で可","原則禁止","自由","消防長許可で可"],"ans":2,"exp":"火気厳禁。"},
{"q":"危険物の運搬で積載方法の原則は？","choices":["横積み","縦積み","重量物下・軽量物上","斜め積み"],"ans":3,"exp":"重い物を下、軽い物を上に。"},
{"q":"危険物の容器表示に必須でないものは？","choices":["品名","成分","指定数量","危険等級"],"ans":3,"exp":"容器表示は品名/危険等級/水溶性/火気厳禁等。指定数量は不要。"},
# ---- 物理化学（19〜34） ----
{"q":"引火点とは？","choices":["自然発火する温度","点火源で燃え続ける最低の液温","爆発下限界","燃焼速度"],"ans":2,"exp":"外部点火で“燃え続ける”最低液温。"},
{"q":"発火点とは？","choices":["自然発火する温度","引火する最低温度","沸点","蒸気圧が1atmとなる温度"],"ans":1,"exp":"外部点火なしで自己発火する温度。"},
{"q":"蒸気圧が高いほど","choices":["蒸発しにくい","引火しにくい","蒸発しやすい","沸点が上がる"],"ans":3,"exp":"蒸気圧↑＝揮発性↑。"},
{"q":"密度が空気より大きい蒸気は？","choices":["上部に滞留","下方に滞留","均一に拡散","滞留しない"],"ans":2,"exp":"多くの第4類蒸気は空気より重く“低所に滞留”。"},
{"q":"爆発下限界に近い混合気は？","choices":["着火しやすい","着火しにくい","必ず爆発","酸欠"],"ans":2,"exp":"下限界付近は可燃性が不足し着火しにくい。"},
{"q":"可燃性液体の蒸気が最も発生しやすいのは？","choices":["表面積大・温度高・風通し良","表面積小・温度低","密閉・低温","表面積小・高湿"],"ans":1,"exp":"表面積↑・温度↑で蒸発↑。"},
{"q":"水に不溶・比重<1の第4類の流出時、堰内でどうなる？","choices":["水層の下に沈む","水面に浮く","水と混ざる","勝手に蒸発する"],"ans":2,"exp":"比重<1・不溶→水面に浮上。"},
{"q":"メタノールの特徴","choices":["毒性なし","水に溶けない","水に任意に混和","比重>1で沈む"],"ans":3,"exp":"メタノールは水と任意混和、毒性あり。"},
{"q":"アセトンの分類","choices":["第1石油類","アルコール類","第2石油類","第3石油類"],"ans":1,"exp":"アセトンは第1石油類（非水溶性ではないが法分類は第1）。"},
{"q":"灯油の指定数量","choices":["200L","400L","1000L","2000L"],"ans":3,"exp":"灯油・軽油は1000L。"},
{"q":"ガソリンの沸点域（概略）","choices":["30〜200℃","-20〜20℃","200〜350℃","80〜120℃"],"ans":1,"exp":"軽質〜中質の広い範囲。"},
{"q":"静電気対策で有効でないもの","choices":["アース","流速を上げる","導電性ホース","加湿"],"ans":2,"exp":"流速を上げると帯電しやすい。"},
{"q":"水溶性第1石油類は？","choices":["ベンゼン","トルエン","酢酸エチル","アセトン"],"ans":4,"exp":"アセトンは水と任意混和。"},
{"q":"酸化剤と混合危険が大きいのは？","choices":["重油","ガソリン","アルコール","アセトアルデヒド"],"ans":4,"exp":"還元性強く酸化剤と激反応。"},
{"q":"ハロゲン化消火剤の主作用","choices":["冷却","窒息","抑制（連鎖反応停止）","希釈"],"ans":3,"exp":"化学抑制効果が主。"},
# ---- 性質・消火（35〜50） ----
{"q":"ガソリン火災に“水散布”は？","choices":["最適","原則禁止","状況により可","水柱で吹き飛ばす"],"ans":2,"exp":"水は比重差で流出拡大の危険。泡で覆う。"},
{"q":"アルコール類に有効な泡は？","choices":["蛋白泡","ケミカル泡","耐アルコール泡","空気泡"],"ans":3,"exp":"耐アルコール泡（アルコール耐性）。"},
{"q":"メタノール火災の消火","choices":["霧状水のみ","二酸化炭素のみ","耐アルコール泡","粉末のみ"],"ans":3,"exp":"耐アルコール泡が第一選択。"},
{"q":"重油の消火に不適","choices":["泡","粉末","二酸化炭素","霧状水"],"ans":3,"exp":"CO₂は開放空間・風で効果薄い。泡が基本。"},
{"q":"静電気着火を防ぐ運用","choices":["満タン直前は高速で注入","金属間のアース","合成樹脂容器の多用","乾燥を保つ"],"ans":2,"exp":"アースと加湿、流速抑制、導電性器具。"},
{"q":"油類流出時の初動","choices":["水で流す","土砂等でせき止め","泡で冷却","蒸気で希釈"],"ans":2,"exp":"まず“止める・囲う”。"},
{"q":"密閉室内の溶剤蒸気対策","choices":["送風して拡散","下部換気を重視","上部のみ排気","加湿だけ"],"ans":2,"exp":"蒸気は重く下部滞留→下方換気。"},
{"q":"アルコール火災で“蛋白泡”のみを使用すると","choices":["問題ない","泡が破壊されやすい","反応爆発","吹き飛ぶ"],"ans":2,"exp":"アルコールで泡が溶解→耐アルコール泡を。"},
{"q":"可燃性液体ポンプ移送時に避けるべきは？","choices":["金属配管","導電性ホース","非導電性ホース","アース接続"],"ans":3,"exp":"非導電性は帯電しやすい。"},
{"q":"引火点が常温より十分高い液体","choices":["常温で引火しやすい","常温では引火しにくい","必ず自然発火","蒸気は空気より軽い"],"ans":2,"exp":"常温で引火点未満なら可燃蒸気が不足。"},
{"q":"アセトアルデヒドの特徴","choices":["常温液体で安定","自己反応性がある","水に不溶で重い","臭気なし"],"ans":2,"exp":"自己反応・重合しやすく危険。"},
{"q":"ベンゼンの性質","choices":["水に任意混和","毒性が強い芳香族","比重1.2で沈む","無引火性"],"ans":2,"exp":"毒性に注意。水にはほぼ不溶。"},
{"q":"塗装ブースの火災主因で誤り","choices":["換気不良","霧化で蒸気濃度上昇","静電気","水分過多"],"ans":4,"exp":"水分は直接の出火原因にならない。"},
{"q":"軽油の指定数量","choices":["200L","400L","1000L","2000L"],"ans":3,"exp":"軽油=1000L。"},
{"q":"第1石油類に該当","choices":["重油","灯油","ガソリン","軽油"],"ans":3,"exp":"ガソリンは第1石油類（非水溶性）。"},
{"q":"水溶性第1石油類の代表","choices":["酢酸エチル","メタノール","ベンゼン","キシレン"],"ans":1,"exp":"酢酸エチルは水にやや溶ける（法上は第1石油類）。"}
]
# ここまでで 50 問

TOTAL = len(Q)  # 50

# -----------------------------
# セッション（超簡易・メモリ）
# -----------------------------
state = {}  # user_id -> {"i":0, "score":0}

def help_text():
    return (
        "📘使い方\n"
        "・「開始」でクイズ開始（全50問）\n"
        "・4択ボタン(1〜4)をタップで回答。手入力 1〜4 でもOK\n"
        "・25問目と50問目で成績を自動集計\n"
        "・「リセット」で最初からやり直し\n"
        "・分野バランスは法令/物理化学/性質消火をミックス\n"
        "※問題文の言い回しや配分は後日調整予定\n"
    )

def quick_for(q):
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label=f"① {q['choices'][0]}", text="1")),
        QuickReplyButton(action=MessageAction(label=f"② {q['choices'][1]}", text="2")),
        QuickReplyButton(action=MessageAction(label=f"③ {q['choices'][2]}", text="3")),
        QuickReplyButton(action=MessageAction(label=f"④ {q['choices'][3]}", text="4")),
        QuickReplyButton(action=MessageAction(label="ヘルプ", text="ヘルプ")),
        QuickReplyButton(action=MessageAction(label="リセット", text="リセット")),
    ])

def send_question(reply_token, uid):
    s = state.setdefault(uid, {"i": 0, "score": 0})
    i = s["i"]
    if i >= TOTAL:
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text=f"全{TOTAL}問お疲れさま！最終成績：{s['score']} / {TOTAL}\n「リセット」で再挑戦できます。")
        )
        return
    q = Q[i]
    text = f"Q{i+1}/{TOTAL}: {q['q']}\n1 {q['choices'][0]}\n2 {q['choices'][1]}\n3 {q['choices'][2]}\n4 {q['choices'][3]}"
    line_bot_api.reply_message(reply_token, TextSendMessage(text=text, quick_reply=quick_for(q)))

def handle_answer(reply_token, uid, choice_num):
    s = state[uid]
    q = Q[s["i"]]
    correct = q["ans"]
    ok = (choice_num == correct)
    if ok:
        s["score"] += 1
        head = "⭕ 正解！"
    else:
        head = f"❌ 不正解… 正解は {correct}：{q['choices'][correct-1]}"
    body = f"(補足) {q['exp']}"
    s["i"] += 1

    # 25 / 50 で総括コメント
    reached = s["i"]
    footer = ""
    if reached in (25, 50):
        footer = f"\n\n— ここまでの成績 —\n{reached}問中 {s['score']} 正解（{round(s['score']/reached*100,1)}%）"
    msg = f"{head}\n{body}{footer}"
    line_bot_api.reply_message(reply_token, TextSendMessage(text=msg))

    # まだ続く場合は次の問題をすぐ出す
    if reached < TOTAL:
        send_question(reply_token, uid)

# -----------------------------
# Webhook
# -----------------------------
@app.post("/callback")
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def on_message(event: MessageEvent):
    uid = event.source.user_id
    text = event.message.text.strip()

    # コマンド
    if text == "ヘルプ":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text()))
        return
    if text == "リセット":
        state[uid] = {"i": 0, "score": 0}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🔁リセットしました。「開始」で再開します。"))
        return
    if text == "開始":
        state.setdefault(uid, {"i": 0, "score": 0})
        send_question(event.reply_token, uid)
        return

    # 回答（1〜4）
    if text in {"1","2","3","4"} and uid in state:
        handle_answer(event.reply_token, uid, int(text))
        return

    # 初回案内
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(
            text="ようこそ！乙4クイズ（全50問）\n「開始」でスタート / 「ヘルプ」で使い方 / 「リセット」で最初から"
        )
    )

# -----------------------------
# run
# -----------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
