import os, csv, pathlib, logging
from flask import Flask, request, jsonify
import requests

# ====== 設定 ======
BASE_DIR = pathlib.Path(__file__).resolve().parent       # /app
DEFAULT_DATA = BASE_DIR / "data" / "otsu4.csv"           # ←CSVは data/ に置く
DATA_FILE = pathlib.Path(os.environ.get("DATA_FILE", str(DEFAULT_DATA)))

CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN", "")
CHANNEL_SECRET       = os.environ.get("CHANNEL_SECRET", "")  # 署名検証は必要なら後で追加

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


# ====== CSVローダ ======
# 形式: (ヘッダ有無どちらも可)
# 問題文,選択肢1,選択肢2,選択肢3,選択肢4,正解番号(1-4)
def load_questions(path: pathlib.Path):
    qs = []
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            rdr = csv.reader(f)
            rows = [r for r in rdr if r and any(c.strip() for c in r)]
            if not rows:
                return []
            # ヘッダ行っぽければ捨てる
            head = [c.strip().lower() for c in rows[0]]
            if "question" in head or "問題文" in head:
                rows = rows[1:]
            for r in rows:
                # 列足りても落ちないようパディング
                r = (r + [""] * 6)[:6]
                qtext = r[0].strip()
                choices = [r[1].strip(), r[2].strip(), r[3].strip(), r[4].strip()]
                try:
                    ans = int(str(r[5]).strip())
                    if ans not in (1,2,3,4): ans = 1
                except Exception:
                    ans = 1
                if qtext:
                    qs.append({"q": qtext, "choices": choices, "answer": ans})
        app.logger.info(f"[CSV] loaded: {len(qs)} from {path}")
    except FileNotFoundError:
        app.logger.error(f"[CSV] NOT FOUND: {path}")
    except Exception as e:
        app.logger.exception(f"[CSV] LOAD ERROR: {e}")
    return qs

QUESTIONS = load_questions(DATA_FILE)


# ====== 返信ユーティリティ ======
def _post_line(url, payload):
    headers = {
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        requests.post(url, headers=headers, json=payload, timeout=10)
    except Exception as e:
        app.logger.error(f"[LINE POST ERROR] {e}")

def reply_text(reply_token: str, text: str):
    _post_line("https://api.line.me/v2/bot/message/reply", {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text}]
    })

# カルーセル（テンプレート）で4択を出す
# ※1列あたりアクション最大3なので、2列に分割（1〜3 / 4）
def reply_question_carousel(reply_token: str, q: dict):
    col1_actions = [
        {"type": "message", "label": f"1) {q['choices'][0]}", "text": "1"},
        {"type": "message", "label": f"2) {q['choices'][1]}", "text": "2"},
        {"type": "message", "label": f"3) {q['choices'][2]}", "text": "3"},
    ]
    col2_actions = [
        {"type": "message", "label": f"4) {q['choices'][3]}", "text": "4"},
    ]
    payload = {
        "replyToken": reply_token,
        "messages": [{
            "type": "template",
            "altText": f"Q: {q['q']}",
            "template": {
                "type": "carousel",
                "columns": [
                    {
                        "title": "問題",
                        "text": q["q"][:60] or "問題",
                        "actions": col1_actions
                    },
                    {
                        "title": "選択肢つづき",
                        "text": "残りの選択肢です",
                        "actions": col2_actions
                    }
                ]
            }
        }]
    }
    _post_line("https://api.line.me/v2/bot/message/reply", payload)


# ====== LINE Webhook ======
def handle_event(ev):
    if ev.get("type") != "message" or ev["message"]["type"] != "text":
        return
    text = (ev["message"].get("text") or "").strip()
    rt = ev["replyToken"]

    if text in ("開始", "スタート", "start", "開始 危険物取扱者 乙4"):
        if not QUESTIONS:
            reply_text(rt, "問題が見つかりません。データファイルを配置してください。")
        else:
            # まず先頭の1問（後でランダム＆重複なしに拡張）
            reply_question_carousel(rt, QUESTIONS[0])
        return

    if text in ("リロード", "reload", "csv再読込"):
        global QUESTIONS
        QUESTIONS = load_questions(DATA_FILE)
        reply_text(rt, f"CSV再読込: {len(QUESTIONS)}問")
        return

    if text in ("ヘルプ", "help"):
        reply_text(rt, "📘使い方\n・『開始』で出題\n・『リロード』でCSV再読込\nCSVは data/otsu4.csv（または環境変数 DATA_FILE）から読み込みます。")
        return

    reply_text(rt, f"あなたのメッセージ: {text}")

@app.post("/")
def webhook_root():
    body = request.get_json(force=True, silent=True) or {}
    for ev in body.get("events", []):
        handle_event(ev)
    return "OK"

@app.post("/callback")
def webhook_callback():
    return webhook_root()  # / と /callback どちらでもOK


# ====== ヘルス／デバッグ ======
@app.get("/")
def health():
    return "OK"

@app.get("/_debug")
def _debug():
    return jsonify({
        "path": str(DATA_FILE),
        "exists": DATA_FILE.exists(),
        "count": len(QUESTIONS),
        "sample": QUESTIONS[0] if QUESTIONS else None
    })
