from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx, time, hmac, hashlib

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
cfg = {}

@app.get("/ping")
async def ping():
    return {"ok": True, "binance": True}

@app.get("/tickers")
async def tickers():
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get("https://api.binance.com/api/v3/ticker/24hr")
        t = {x["symbol"]: {"price": float(x["lastPrice"]), "chg": float(x["priceChangePercent"]), "vol": float(x["quoteVolume"])} for x in r.json() if x["symbol"].endswith("USDT")}
        return {"ok": True, "tickers": t}

@app.post("/config")
async def config(body: dict):
    cfg.update(body)
    return {"ok": True, "message": "Keys saved"}

@app.get("/balance")
async def balance():
    return {"ok": True, "usdt": 0}
