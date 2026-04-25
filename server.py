from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import hmac
import hashlib
import time

app = FastAPI(title=“CryptoBot API”)

app.add_middleware(
CORSMiddleware,
allow_origins=[”*”],
allow_credentials=True,
allow_methods=[”*”],
allow_headers=[”*”],
)

BASE = “https://api.binance.com”
cfg = {“api_key”: “”, “api_secret”: “”}

def sign(params, secret):
q = “&”.join(f”{k}={v}” for k, v in params.items())
return hmac.new(secret.encode(), q.encode(), hashlib.sha256).hexdigest()

def ts():
return int(time.time() * 1000)

@app.get(”/ping”)
async def ping():
try:
async with httpx.AsyncClient(timeout=10) as c:
r = await c.get(f”{BASE}/api/v3/ping”)
return {“ok”: True, “binance”: r.status_code == 200}
except:
return {“ok”: True, “binance”: False}

@app.post(”/config”)
async def config(body: dict):
cfg[“api_key”] = body.get(“api_key”, “”)
cfg[“api_secret”] = body.get(“api_secret”, “”)
if cfg[“api_key”] and cfg[“api_secret”]:
try:
params = {“timestamp”: ts()}
params[“signature”] = sign(params, cfg[“api_secret”])
async with httpx.AsyncClient(timeout=10) as c:
r = await c.get(f”{BASE}/api/v3/account”,
params=params,
headers={“X-MBX-APIKEY”: cfg[“api_key”]})
if r.status_code == 200:
return {“ok”: True, “message”: “API keys verified successfully!”}
else:
d = r.json()
return {“ok”: False, “message”: f”Invalid keys: {d.get(‘msg’,’’)}”}
except Exception as e:
return {“ok”: False, “message”: str(e)}
return {“ok”: True, “message”: “Saved (Paper trading mode)”}

@app.get(”/tickers”)
async def tickers():
try:
async with httpx.AsyncClient(timeout=15) as c:
r = await c.get(f”{BASE}/api/v3/ticker/24hr”)
data = r.json()
result = {}
for t in data:
if t[“symbol”].endswith(“USDT”):
result[t[“symbol”]] = {
“price”: float(t[“lastPrice”]),
“chg”: float(t[“priceChangePercent”]),
“high”: float(t[“highPrice”]),
“low”: float(t[“lowPrice”]),
“vol”: float(t[“quoteVolume”]),
}
return {“ok”: True, “tickers”: result}
except Exception as e:
raise HTTPException(500, str(e))

@app.get(”/balance”)
async def balance():
if not cfg[“api_key”]:
return {“ok”: False, “usdt”: 0, “message”: “No API keys”}
try:
params = {“timestamp”: ts()}
params[“signature”] = sign(params, cfg[“api_secret”])
async with httpx.AsyncClient(timeout=10) as c:
r = await c.get(f”{BASE}/api/v3/account”,
params=params,
headers={“X-MBX-APIKEY”: cfg[“api_key”]})
data = r.json()
usdt = next((float(b[“free”]) for b in data[“balances”] if b[“asset”] == “USDT”), 0)
return {“ok”: True, “usdt”: usdt}
except Exception as e:
raise HTTPException(500, str(e))

@app.post(”/order”)
async def order(body: dict):
if not cfg[“api_key”]:
return {“ok”: False, “message”: “No API keys configured”}
try:
params = {
“symbol”: body[“symbol”],
“side”: body[“side”],
“type”: body.get(“type”, “MARKET”),
“timestamp”: ts()
}
if “quoteOrderQty” in body:
params[“quoteOrderQty”] = body[“quoteOrderQty”]
elif “quantity” in body:
params[“quantity”] = body[“quantity”]
params[“signature”] = sign(params, cfg[“api_secret”])
async with httpx.AsyncClient(timeout=15) as c:
r = await c.post(f”{BASE}/api/v3/order”,
data=params,
headers={“X-MBX-APIKEY”: cfg[“api_key”]})
result = r.json()
if r.status_code == 200:
fills = result.get(“fills”, [{}])
price = float(fills[0].get(“price”, 0)) if fills else 0
return {“ok”: True, “orderId”: result[“orderId”],
“price”: price, “qty”: float(result[“executedQty”]),
“status”: result[“status”]}
else:
return {“ok”: False, “message”: result.get(“msg”, “Order failed”)}
except Exception as e:
return {“ok”: False, “message”: str(e)}

if **name** == “**main**”:
import uvicorn
uvicorn.run(app, host=“0.0.0.0”, port=8000)
