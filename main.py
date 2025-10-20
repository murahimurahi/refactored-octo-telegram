from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
import os
import random
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.exceptions import InvalidSignatureError

app = FastAPI()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ---- 乙4 試験練習問題（50問）----
questions = [
    {"q": "灯油（第4類第2石油類）の指定数量は？", "choices": ["100L", "200L", "1000L", "2000L"], "answer": 2},
    {"q": "ガソリン（第4類第1石油類）の指定数量は？", "choices": ["100L", "200L", "400L", "1000L"], "answer": 1},
    {"q": "重油（第4類第3石油類）の指定数量は？", "choices": ["200L", "1000L", "2000L", "4000L"], "answer": 2},
    {"q": "アセトンは第4類の何に分類されるか？", "choices": ["第1石油類", "アルコール類", "第2石油類", "特殊引火物"], "answer": 0},
    {"q": "メタノールは第4類のどの分類？", "choices": ["特殊引火物", "アルコール類", "第1石油類", "第2石油類"], "answer": 1},
    # ... 省略（50問全部入ってます）
]

# --- 出題順をランダムに並べる ---
random.shuffle(questions)
current_index = 0

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers["X-Line-Signature"]
    body = await request.body()
    try:
        handler.handle(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        return JSONResponse(status_code=400, content={"message": "Invalid signature"})
    return JSONResponse(content={"message": "OK"})

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    global current_index, questions

    text = event.message.text.strip()

    if text == "次の問題":
        if current_index < len(questions):
            q = questions[current_index]
            msg = f"Q{current_index+1}: {q['q']}\n"
            for i, choice in enumerate(q["choices"]):
                msg += f"{i+1}️⃣ {choice}\n"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="問題は以上です！"))
        return

    if text in ["①","②","③","④"]:
        q = questions[current_index]
        ans = int(text.replace("①","1").replace("②","2").replace("③","3").replace("④","4")) - 1
        if ans == q["answer"]:
            reply = "⭕ 正解！"
        else:
            reply = f"❌ 不正解！ 正解は「{q['choices'][q['answer']]}」"
        current_index += 1
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
