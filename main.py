from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

# 動作確認用
@app.get("/health")
async def health():
    return {"status": "ok"}

# LINEのWebhook受け取り用
@app.post("/callback")
async def callback(request: Request):
    body = await request.body()
    # とりあえず受け取ったら200で返す
    print("Webhook received:", body.decode("utf-8"))
    return JSONResponse(content={"message": "OK"}, status_code=200)
