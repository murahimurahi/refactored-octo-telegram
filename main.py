import os
from flask import Flask, request, abort, Response
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage,
    QuickReply, QuickReplyButton, MessageAction, URIAction
)

app = Flask(__name__)

# ---- LINE Secrets ----
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ---- In-memory session (簡易) ----
sessions = {}  # {user_id: {"index": int, "score": int, "answered": int}}

def sess(user_id):
    if user_id not in sessions:
        sessions[user_id] = {"index": 0, "score": 0, "answered": 0}
    return sessions[user_id]

# ---- 乙4 過去問風 50問（数字を避けた概念中心・誤りにくい内容）----
# ans は 1~4 の整数
questions = [
    {"q": "引火点とは？", "choices": ["自然に燃え出す温度", "火源があれば燃える最も低い温度", "沸騰を始める温度", "燃焼が継続する温度"], "ans": 2, "exp": "引火点は火源があると蒸気に着火する最低温度。"},
    {"q": "発火点とは？", "choices": ["自然に燃え出す最低温度", "鍋が熱くなる温度", "液体が沸騰する温度", "固体が溶ける温度"], "ans": 1, "exp": "外部火源なしで自然に発火する最低温度。"},
    {"q": "可燃性蒸気は空気より重いことが多く、何にたまりやすい？", "choices": ["高い場所", "低い場所", "どこにもたまらない", "水面上"], "ans": 2, "exp": "多くの可燃性蒸気は比重が空気より大きく低所へ滞留。"},
    {"q": "静電気による火花放電を防ぐ基本は？", "choices": ["換気を止める", "接地・等電位化", "加熱する", "湿度を下げる"], "ans": 2, "exp": "接地・等電位化と湿度管理が有効。"},
    {"q": "第4類危険物の共通性質は？", "choices": ["酸化性が強い", "可燃性の液体", "毒性が強い", "腐食性のみ"], "ans": 2, "exp": "乙4は『可燃性液体』を扱う資格。"},
    {"q": "燃焼の三要素は？", "choices": ["熱・酸素・可燃物", "熱・窒素・可燃物", "光・酸素・水", "電気・水・風"], "ans": 1, "exp": "熱源・酸素供給・可燃物が必要。"},
    {"q": "水で消火してはいけないのは？", "choices": ["油火災", "紙の火災", "木材の火災", "布の火災"], "ans": 1, "exp": "油は水に浮き飛散し拡大する。"},
    {"q": "泡消火薬剤の主目的は？", "choices": ["酸素供給", "冷却", "窒息・遮断と冷却", "加熱"], "ans": 3, "exp": "表面に膜や泡層を作り窒息＋冷却。"},
    {"q": "金属ナトリウムに適さない消火剤は？", "choices": ["乾燥砂", "粉末", "水", "金属火災用粉末"], "ans": 3, "exp": "水と激しく反応し危険。"},
    {"q": "蒸気圧が高い液体は一般に？", "choices": ["気化しにくい", "気化しやすい", "引火しない", "沸点が必ず高い"], "ans": 2, "exp": "蒸気圧が高いほど蒸発しやすい。"},
    {"q": "換気の目的で正しいのは？", "choices": ["蒸気濃度を上げる", "蒸気を希釈・排出する", "温度を上げる", "静電気を発生させる"], "ans": 2, "exp": "発生蒸気を希釈排出し爆発限界未満へ。"},
    {"q": "危険物標識『火気厳禁』の色は？", "choices": ["青地白字", "赤地白字", "緑地白字", "黄地黒字"], "ans": 2, "exp": "赤地白字が一般的。"},
    {"q": "危険物の類別表示で『第4類』の色は？", "choices": ["青", "赤", "黄", "緑"], "ans": 1, "exp": "類別標識は第1類：黄、第2：黄、第3：青、第4：青 など自治体様式に準ず。"},
    {"q": "引火点が低いほど？", "choices": ["危険性は低い", "危険性は高い", "変わらない", "燃えない"], "ans": 2, "exp": "低温でも着火しやすく危険性が高い。"},
    {"q": "指定数量の意義は？", "choices": ["最大保管可能量", "法規制強化の境界量", "販売価格", "比重"], "ans": 2, "exp": "指定数量以上は許可・設備が必要。"},
    {"q": "危険物の貯蔵所で容器に求められるのは？", "choices": ["強度・気密・表示", "透明で軽いこと", "金属製のみ", "紙製のみ"], "ans": 1, "exp": "内容物適合の材質・強度・表示が必要。"},
    {"q": "屋内貯蔵所で原則必要な設備は？", "choices": ["加熱炉", "換気設備・消火設備", "冷蔵庫のみ", "飾り棚"], "ans": 2, "exp": "自然換気/機械換気や消火設備が必要。"},
    {"q": "危険物の運搬で注意すべきは？", "choices": ["容器の転倒防止", "密栓しない", "ラベル除去", "日光に当てる"], "ans": 1, "exp": "堅固に固定し密栓・表示を保持。"},
    {"q": "作業前の静電気対策で有効なのは？", "choices": ["合成繊維の着用", "導電靴・接地", "乾燥環境", "ビニール手袋"], "ans": 2, "exp": "導電性の履物・床・接地が基本。"},
    {"q": "油吸着材の処理で正しいのは？", "choices": ["排水へ流す", "可燃ごみ", "危険物として適正処理", "乾燥させて放置"], "ans": 3, "exp": "汚染物も危険物に準じ管理。"},
    # 20
    {"q": "蒸気はどこに滞留しやすい？", "choices": ["天井付近", "床付近", "窓付近", "屋外のみ"], "ans": 2, "exp": "比重が大きい蒸気は低所に滞留。"},
    {"q": "漏えい時の第一行動は？", "choices": ["スマホ撮影", "喫煙", "着火源排除と換気・避難", "加熱"], "ans": 3, "exp": "着火源除去・排気・安全確保が最優先。"},
    {"q": "金属容器の液面計測で安全なのは？", "choices": ["裸電球を入れる", "鉄棒で撹拌", "導電性のあるアース済み計器", "火を近づける"], "ans": 3, "exp": "静電火花を防ぐ。"},
    {"q": "可燃性蒸気の爆発下限界より下の濃度では？", "choices": ["燃焼しない", "常に爆発する", "必ず自然発火", "色が変わる"], "ans": 1, "exp": "下限界未満では可燃範囲外。"},
    {"q": "容器ラベルの基本情報は？", "choices": ["製造者の趣味", "内容物名・危険区分・注意", "価格のみ", "QRのみ"], "ans": 2, "exp": "内容物/類項/注意/連絡先など。"},
    {"q": "火災四分類で油火災は？", "choices": ["A(普通)", "B(油)", "C(電気)", "D(金属)"], "ans": 2, "exp": "油火災はB火災。"},
    {"q": "電気火災への水噴霧は？", "choices": ["感電の恐れ", "安全", "推奨", "必須"], "ans": 1, "exp": "感電・短絡の恐れ。電源遮断を優先。"},
    {"q": "換気扇のスイッチ操作は漏えい時に？", "choices": ["火花の恐れに注意", "必ず入れる", "必ず切る", "関係ない"], "ans": 1, "exp": "防爆でないスイッチ操作は火花要注意。"},
    {"q": "防爆構造機器の目的は？", "choices": ["耐震", "着火源抑止", "防水", "遮音"], "ans": 2, "exp": "爆発性雰囲気での着火源抑制。"},
    {"q": "皮膚に溶剤が付いたら？", "choices": ["乾くまで放置", "火であぶる", "大量の水で洗う", "布でこする"], "ans": 3, "exp": "流水で速やかに洗浄。"},
    # 30
    {"q": "可燃液体の保管温度で望ましいのは？", "choices": ["高温", "直射日光", "常温・低温で安定", "加熱保持"], "ans": 3, "exp": "温度上昇は蒸気増加＝危険。"},
    {"q": "容器のアース線は？", "choices": ["飾り", "等電位結合に必要", "不要", "絶縁すべき"], "ans": 2, "exp": "容器・配管・機器を等電位化。"},
    {"q": "開放系での液移送中に危険な行為は？", "choices": ["接地", "金属同士の接触維持", "ポリ容器を空中で注ぐ", "静かに注ぐ"], "ans": 3, "exp": "空中注ぎは帯電・飛散を招く。"},
    {"q": "油の自然発火を招くのは？", "choices": ["酸素不足", "含浸したウエスの放置", "冷凍保存", "水濡れ"], "ans": 2, "exp": "乾性油を含んだ布の山は危険。"},
    {"q": "アルコール類の特徴は？", "choices": ["水に溶けない", "水に溶けやすいものが多い", "固体が多い", "可燃性がない"], "ans": 2, "exp": "多くは水混和性で可燃。"},
    {"q": "消防法で『屋外タンク貯蔵所』の利点は？", "choices": ["近隣影響大", "自然換気しやすい", "屋内より蒸気がこもる", "雨水で満たす"], "ans": 2, "exp": "開放空間で蒸気滞留しにくい。"},
    {"q": "少量危険物の扱いは？", "choices": ["規制が全くない", "都道府県条例で基準あり", "自由に野積み", "名称表示不要"], "ans": 2, "exp": "条例に基づく基準が定められる。"},
    {"q": "移送ポンプ停止時の手順は？", "choices": ["電源OFFのみ", "吸込管開放", "バルブ閉＆電源OFF", "開放して放置"], "ans": 3, "exp": "バルブ閉止・電源遮断など安全操作。"},
    {"q": "油類の比重は一般に？", "choices": ["水より重い", "水と同じ", "水より軽いものが多い", "必ず気体"], "ans": 3, "exp": "多くは水より軽く水面に浮く。"},
    {"q": "沸点が低い液体は？", "choices": ["蒸気が出にくい", "蒸気が出やすい", "可燃性がない", "固体化する"], "ans": 2, "exp": "気化しやすく注意。"},
    # 40
    {"q": "爆発上限界を超える高濃度では？", "choices": ["爆発しない場合がある", "必ず爆発", "燃えない", "青色になる"], "ans": 1, "exp": "濃すぎても酸素不足で燃えにくい。"},
    {"q": "局所排気フードの目的は？", "choices": ["蒸気を捕集・排出", "加湿", "加熱", "点火"], "ans": 1, "exp": "発生源近傍で捕集し拡散防止。"},
    {"q": "容器洗浄で避けるのは？", "choices": ["密閉空間での作業", "換気", "防護具", "表示残し"], "ans": 1, "exp": "酸欠・蒸気暴露の危険。"},
    {"q": "安全データシート(SDS)の目的は？", "choices": ["価格交渉", "物性・危険性・応急措置等の情報提供", "広告", "在庫管理"], "ans": 2, "exp": "SDSで危険性や対策を共有。"},
    {"q": "保護具で最優先は？", "choices": ["おしゃれ", "用途適合の選定", "サイズ自由", "使い捨て必須"], "ans": 2, "exp": "物質・作業に応じた適合が重要。"},
    {"q": "雷注意報時の屋外移送は？", "choices": ["積極的に行う", "火花対策を強化・延期検討", "影響なし", "必ず中止"], "ans": 2, "exp": "誘導雷・静電気に注意。"},
    {"q": "容器の保管姿勢で望ましいのは？", "choices": ["不安定でもOK", "転倒防止・直立", "常に横倒し", "蓋を緩める"], "ans": 2, "exp": "転倒防止・密栓・表示面外向き等。"},
    {"q": "漏れの見つけ方で危険なのは？", "choices": ["泡立ち試験", "臭気の確認", "火を近づける", "検知器使用"], "ans": 3, "exp": "着火の恐れ。"},
    {"q": "こぼれた油の初期対応は？", "choices": ["水で流す", "吸着材で囲い回収", "扇風機で飛ばす", "放置"], "ans": 2, "exp": "吸着・囲い込み・回収・適正処理。"},
    {"q": "教育・訓練の目的は？", "choices": ["記念写真", "危険の理解と手順遵守", "懇親", "休暇取得"], "ans": 2, "exp": "手順理解と実行が事故防止に直結。"},
    # 50
]
TOTAL = len(questions)

# ---- Flex builders ----
def flex_mid_summary(score, answered, base_url):
    return {
        "type": "bubble",
        "size": "mega",
        "header": {"type": "box", "layout": "vertical", "contents": [
            {"type": "text", "text": "🎉 25問クリア！", "weight": "bold", "size": "lg"}
        ]},
        "body": {"type": "box", "layout": "vertical", "contents": [
            {"type": "text", "text": f"ここまでの正解数：{score}/{answered}"},
            {"type": "text", "text": f"正答率：{round(100*score/max(1,answered))}%"},
            {"type": "separator", "margin": "md"},
            {"type": "text", "text": "続きは『次の問題』でどうぞ。", "wrap": True}
        ]},
        "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
            {"type": "button", "action": {"type": "uri", "label": "お祝いを見る 🎊",
                                          "uri": f"{base_url}/celebrate?m=mid"}, "style": "primary"}
        ]}
    }

def flex_final_summary(score, total, base_url):
    return {
        "type": "bubble",
        "size": "mega",
        "header": {"type": "box", "layout": "vertical", "contents": [
            {"type": "text", "text": "🎊 全問終了！", "weight": "bold", "size": "lg"}
        ]},
        "body": {"type": "box", "layout": "vertical", "contents": [
            {"type": "text", "text": f"最終成績：{score}/{total}"},
            {"type": "text", "text": f"正答率：{round(100*score/max(1,total))}%"},
            {"type": "separator", "margin": "md"},
            {"type": "text", "text": "『リセット』で最初から再挑戦できます。", "wrap": True}
        ]},
        "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
            {"type": "button", "action": {"type": "uri", "label": "紙吹雪でお祝い 🎉",
                                          "uri": f"{base_url}/celebrate?m=final"}, "style": "primary"}
        ]}
    }

def make_question(s):
    if s["index"] >= TOTAL:
        return None
    q = questions[s["index"]]
    text = f"Q{s['index']+1}/{TOTAL}: {q['q']}\n"
    for i, c in enumerate(q["choices"], start=1):
        text += f"{i}. {c}\n"
    text += "（1～4で回答）"
    return text

# ---- Healthcheck ----
@app.get("/health")
def health():
    return {"status": "ok"}

# ---- Celebrate page (紙吹雪) ----
# LINE内ブラウザで開いて紙吹雪アニメを表示
@app.get("/celebrate")
def celebrate():
    html = """<!doctype html>
<html lang="ja"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>おめでとう！</title>
<style>
body{margin:0;font-family:sans-serif;background:#111;color:#fff;display:flex;align-items:center;justify-content:center;height:100vh;overflow:hidden}
.box{text-align:center}
h1{font-size:28px;margin:10px 0}
p{opacity:.85}
.btn{display:inline-block;margin-top:16px;padding:10px 16px;background:#06c167;color:#fff;border-radius:8px;text-decoration:none}
small{display:block;margin-top:12px;opacity:.7}
canvas{position:fixed;inset:0;pointer-events:none}
</style>
</head>
<body>
<canvas id="cnf"></canvas>
<div class="box">
  <h1>🎉 おめでとう！ 🎉</h1>
  <p>がんばりを称えて紙吹雪をプレゼント！</p>
  <a class="btn" href="line://msg/text/次の問題">LINEに戻る</a>
  <small>ボタンで戻れない時は画面を閉じてください。</small>
</div>
<script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.9.3/dist/confetti.browser.min.js"></script>
<script>
const duration = 4000;
const end = Date.now() + duration;
(function frame(){
  confetti({particleCount: 3, angle: 60, spread: 55, origin: {x: 0}});
  confetti({particleCount: 3, angle: 120, spread: 55, origin: {x: 1}});
  if (Date.now() < end) requestAnimationFrame(frame);
})();
</script>
</body></html>"""
    return Response(html, mimetype="text/html; charset=utf-8")

# ---- LINE Webhook ----
@app.route("/callback", methods=["POST"])
def callback():
    sig = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, sig)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def on_message(event: MessageEvent):
    user_id = event.source.user_id
    s = sess(user_id)
    text = event.message.text.strip()

    # ベースURL（Flexボタンの遷移先に使う）
    # Renderなどは環境変数に入れておくと確実。未設定時は推測不可なので相対でOK。
    base_url = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    if not base_url:
        # 既知URLがない場合は Render 等の公開URLを直接入れてください。
        # 例: os.environ["PUBLIC_BASE_URL"]="https://xxxxx.onrender.com"
        base_url = ""

    # ---- コマンド ----
    if text == "リセット":
        sessions[user_id] = {"index": 0, "score": 0, "answered": 0}
        line_bot_api.reply_message(event.reply_token, TextSendMessage("セッションをリセットしました。『次の問題』で再開できます。"))
        return

    if text == "成績確認":
        pct = round(100 * s["score"] / max(1, s["answered"]))
        line_bot_api.reply_message(event.reply_token,
            TextSendMessage(f"累積成績：{s['answered']}問中 {s['score']}問正解（{pct}%）"))
        return

    if text == "次の問題":
        qtext = make_question(s)
        if qtext:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(qtext))
        else:
            # すでに全問終了
            flex = flex_final_summary(s["score"], TOTAL, base_url)
            line_bot_api.reply_message(event.reply_token,
                FlexSendMessage(alt_text="全問終了！", contents=flex))
        return

    if text == "ヘルプ":
        help_msg = ("使い方：\n"
                    "・『次の問題』で出題\n"
                    "・1～4 で回答\n"
                    "・『成績確認』で途中結果\n"
                    "・『リセット』で最初から\n"
                    "※正解/不正解の後は『リセット』『ヘルプ』のみが出ます。")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(help_msg))
        return

    # ---- 回答（数字）----
    if text.isdigit():
        if s["index"] < TOTAL:
            q = questions[s["index"]]
            ans = int(text)
            s["answered"] += 1
            if ans == q["ans"]:
                s["score"] += 1
                feedback = "⭕ 正解！"
            else:
                feedback = ("❌ 不正解…\n"
                            f"正解は {q['ans']} : {q['choices'][q['ans']-1]}\n"
                            f"(補足) {q['exp']}")

            # 正解/不正解直後は リセット と ヘルプのみ
            qr = QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="リセット", text="リセット")),
                QuickReplyButton(action=MessageAction(label="ヘルプ", text="ヘルプ")),
            ])
            line_bot_api.reply_message(event.reply_token, TextSendMessage(feedback, quick_reply=qr))

            s["index"] += 1

            # 25問総括（押しメッセージ）
            if s["index"] == 25:
                flex = flex_mid_summary(s["score"], s["answered"], base_url)
                line_bot_api.push_message(user_id, FlexSendMessage(alt_text="25問クリア！", contents=flex))

            # 50問（最終）総括
            if s["index"] == TOTAL:
                flex = flex_final_summary(s["score"], TOTAL, base_url)
                line_bot_api.push_message(user_id, FlexSendMessage(alt_text="全問終了！", contents=flex))
        return

if __name__ == "__main__":
    # Render等で PORT が与えられる想定
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
