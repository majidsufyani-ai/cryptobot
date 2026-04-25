# “””
بوت التداول الشامل - Backend Server

يجلب أسعار حقيقية من Binance ويوفرها للبوت
بدون قيود CORS

تثبيت المتطلبات:
pip install fastapi uvicorn httpx python-binance websockets

تشغيل:
python server.py
“””

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import asyncio
import time
import hmac
import hashlib
import json
from typing import Optional
from datetime import datetime

# ─── Binance API ───────────────────────────────────

BINANCE_BASE = “https://api.binance.com”
BINANCE_WS   = “wss://stream.binance.com:9443”

app = FastAPI(title=“بوت التداول - Backend”, version=“4.0”)

# السماح للمتصفح بالاتصال (CORS)

app.add_middleware(
CORSMiddleware,
allow_origins=[”*”],          # في الإنتاج: ضع عنوان موقعك فقط
allow_credentials=True,
allow_methods=[”*”],
allow_headers=[”*”],
)

# ─── تخزين البيانات في الذاكرة ─────────────────────

cache = {
“tickers”: {},          # {symbol: ticker_data}
“tickers_updated”: 0,   # unix timestamp
“pairs”: [],            # قائمة كل أزواج USDT
“pairs_updated”: 0,
}

config = {
“api_key”: “”,
“api_secret”: “”,
}

# ─── مساعد: توقيع طلبات Binance ────────────────────

def sign(params: dict, secret: str) -> str:
query = “&”.join(f”{k}={v}” for k, v in params.items())
return hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()

def ts() -> int:
return int(time.time() * 1000)

# ─── طلب HTTP عام ──────────────────────────────────

async def binance_get(path: str, params: dict = None, signed: bool = False) -> dict:
url = BINANCE_BASE + path
headers = {}
p = params or {}

```
if config["api_key"]:
    headers["X-MBX-APIKEY"] = config["api_key"]

if signed and config["api_secret"]:
    p["timestamp"] = ts()
    p["signature"] = sign(p, config["api_secret"])

async with httpx.AsyncClient(timeout=15) as client:
    r = await client.get(url, params=p, headers=headers)
    r.raise_for_status()
    return r.json()
```

async def binance_post(path: str, params: dict = None) -> dict:
url = BINANCE_BASE + path
headers = {“X-MBX-APIKEY”: config[“api_key”]}
p = params or {}
p[“timestamp”] = ts()
p[“signature”] = sign(p, config[“api_secret”])

```
async with httpx.AsyncClient(timeout=15) as client:
    r = await client.post(url, data=p, headers=headers)
    r.raise_for_status()
    return r.json()
```

async def binance_delete(path: str, params: dict = None) -> dict:
url = BINANCE_BASE + path
headers = {“X-MBX-APIKEY”: config[“api_key”]}
p = params or {}
p[“timestamp”] = ts()
p[“signature”] = sign(p, config[“api_secret”])

```
async with httpx.AsyncClient(timeout=15) as client:
    r = await client.delete(url, params=p, headers=headers)
    r.raise_for_status()
    return r.json()
```

# ════════════════════════════════════════════════════

# ENDPOINTS

# ════════════════════════════════════════════════════

# ─── ping ───────────────────────────────────────────

@app.get(”/ping”)
async def ping():
try:
await binance_get(”/api/v3/ping”)
return {“ok”: True, “binance”: True, “time”: datetime.now().isoformat()}
except Exception as e:
return {“ok”: True, “binance”: False, “error”: str(e)}

# ─── حفظ مفاتيح API ────────────────────────────────

@app.post(”/config”)
async def set_config(body: dict):
config[“api_key”]    = body.get(“api_key”, “”)
config[“api_secret”] = body.get(“api_secret”, “”)

```
# اختبار المفاتيح
if config["api_key"] and config["api_secret"]:
    try:
        await binance_get("/api/v3/account", signed=True)
        return {"ok": True, "message": "✅ مفاتيح API صحيحة"}
    except Exception as e:
        return {"ok": False, "message": "❌ مفاتيح خاطئة: " + str(e)}
return {"ok": True, "message": "✅ تم الحفظ (بدون مفاتيح — وضع تجريبي)"}
```

# ─── كل أزواج USDT ──────────────────────────────────

@app.get(”/pairs”)
async def get_pairs():
now = time.time()
# cache لمدة 10 دقائق
if cache[“pairs”] and now - cache[“pairs_updated”] < 600:
return {“ok”: True, “pairs”: cache[“pairs”], “count”: len(cache[“pairs”])}

```
try:
    data = await binance_get("/api/v3/exchangeInfo")
    pairs = [
        s["symbol"] for s in data["symbols"]
        if s["quoteAsset"] == "USDT"
        and s["status"] == "TRADING"
        and "SPOT" in s.get("permissions", [])
    ]
    pairs.sort()
    cache["pairs"] = pairs
    cache["pairs_updated"] = now
    return {"ok": True, "pairs": pairs, "count": len(pairs)}
except Exception as e:
    raise HTTPException(500, detail=str(e))
```

# ─── أسعار 24 ساعة لكل العملات ─────────────────────

@app.get(”/tickers”)
async def get_tickers():
now = time.time()
# cache لمدة 10 ثوانٍ
if cache[“tickers”] and now - cache[“tickers_updated”] < 10:
return {“ok”: True, “tickers”: cache[“tickers”], “count”: len(cache[“tickers”])}

```
try:
    data = await binance_get("/api/v3/ticker/24hr")
    result = {}
    for t in data:
        sym = t["symbol"]
        if sym.endswith("USDT"):
            result[sym] = {
                "price":  float(t["lastPrice"]),
                "chg":    float(t["priceChangePercent"]),
                "high":   float(t["highPrice"]),
                "low":    float(t["lowPrice"]),
                "vol":    float(t["quoteVolume"]),
                "open":   float(t["openPrice"]),
                "trades": int(t["count"]),
            }
    cache["tickers"] = result
    cache["tickers_updated"] = now
    return {"ok": True, "tickers": result, "count": len(result)}
except Exception as e:
    raise HTTPException(500, detail=str(e))
```

# ─── سعر عملة واحدة ─────────────────────────────────

@app.get(”/price/{symbol}”)
async def get_price(symbol: str):
try:
data = await binance_get(”/api/v3/ticker/price”, {“symbol”: symbol.upper()})
return {“ok”: True, “symbol”: symbol, “price”: float(data[“price”])}
except Exception as e:
raise HTTPException(500, detail=str(e))

# ─── بيانات الشموع (Klines) ─────────────────────────

@app.get(”/klines/{symbol}”)
async def get_klines(symbol: str, interval: str = “5m”, limit: int = 100):
try:
data = await binance_get(”/api/v3/klines”, {
“symbol”: symbol.upper(),
“interval”: interval,
“limit”: limit
})
candles = [{
“t”:    c[0],
“open”: float(c[1]),
“high”: float(c[2]),
“low”:  float(c[3]),
“close”:float(c[4]),
“vol”:  float(c[5]),
} for c in data]
return {“ok”: True, “symbol”: symbol, “candles”: candles}
except Exception as e:
raise HTTPException(500, detail=str(e))

# ─── معلومات الحساب ──────────────────────────────────

@app.get(”/account”)
async def get_account():
if not config[“api_key”]:
return {“ok”: False, “message”: “لا توجد مفاتيح API”}
try:
data = await binance_get(”/api/v3/account”, signed=True)
balances = {
b[“asset”]: {
“free”:   float(b[“free”]),
“locked”: float(b[“locked”]),
}
for b in data[“balances”]
if float(b[“free”]) > 0 or float(b[“locked”]) > 0
}
return {
“ok”: True,
“balances”: balances,
“canTrade”: data[“canTrade”],
“canWithdraw”: data[“canWithdraw”],
}
except Exception as e:
raise HTTPException(500, detail=str(e))

# ─── رصيد USDT ───────────────────────────────────────

@app.get(”/balance”)
async def get_balance():
if not config[“api_key”]:
return {“ok”: False, “usdt”: 0, “message”: “لا توجد مفاتيح API”}
try:
data = await binance_get(”/api/v3/account”, signed=True)
usdt = next(
(float(b[“free”]) for b in data[“balances”] if b[“asset”] == “USDT”), 0.0
)
return {“ok”: True, “usdt”: usdt}
except Exception as e:
raise HTTPException(500, detail=str(e))

# ─── إنشاء أمر تداول ────────────────────────────────

@app.post(”/order”)
async def create_order(body: dict):
“””
body: {
symbol: “BTCUSDT”,
side: “BUY” | “SELL”,
type: “MARKET” | “LIMIT”,
quantity: “0.001”,         // أو
quoteOrderQty: “100”,      // مبلغ بالـ USDT (للشراء)
price: “67000”,            // للأوامر المحددة فقط
stopPrice: “66000”,        // اختياري
}
“””
if not config[“api_key”] or not config[“api_secret”]:
return {“ok”: False, “message”: “❌ لا توجد مفاتيح API — تداول حقيقي غير متاح”}

```
try:
    params = {
        "symbol":    body["symbol"].upper(),
        "side":      body["side"].upper(),
        "type":      body.get("type", "MARKET"),
    }

    # تحديد الكمية
    if "quoteOrderQty" in body:
        params["quoteOrderQty"] = body["quoteOrderQty"]  # مبلغ USDT
    elif "quantity" in body:
        params["quantity"] = body["quantity"]

    if params["type"] == "LIMIT":
        params["price"]       = body["price"]
        params["timeInForce"] = body.get("timeInForce", "GTC")

    result = await binance_post("/api/v3/order", params)
    return {
        "ok": True,
        "orderId":     result["orderId"],
        "symbol":      result["symbol"],
        "side":        result["side"],
        "status":      result["status"],
        "price":       float(result.get("price") or result.get("fills", [{}])[0].get("price", 0)),
        "qty":         float(result["executedQty"]),
        "time":        result["transactTime"],
    }
except httpx.HTTPStatusError as e:
    err = e.response.json()
    raise HTTPException(400, detail=f"Binance Error {err.get('code')}: {err.get('msg')}")
except Exception as e:
    raise HTTPException(500, detail=str(e))
```

# ─── إلغاء أمر ───────────────────────────────────────

@app.delete(”/order/{symbol}/{order_id}”)
async def cancel_order(symbol: str, order_id: int):
if not config[“api_key”]:
return {“ok”: False, “message”: “لا توجد مفاتيح API”}
try:
result = await binance_delete(”/api/v3/order”, {
“symbol”: symbol.upper(),
“orderId”: order_id
})
return {“ok”: True, “status”: result[“status”]}
except Exception as e:
raise HTTPException(500, detail=str(e))

# ─── سجل الأوامر ─────────────────────────────────────

@app.get(”/orders/{symbol}”)
async def get_orders(symbol: str, limit: int = 20):
if not config[“api_key”]:
return {“ok”: False, “orders”: []}
try:
data = await binance_get(”/api/v3/allOrders”, {
“symbol”: symbol.upper(),
“limit”: limit
}, signed=True)
orders = [{
“id”:     o[“orderId”],
“symbol”: o[“symbol”],
“side”:   o[“side”],
“type”:   o[“type”],
“status”: o[“status”],
“price”:  float(o[“price”]),
“qty”:    float(o[“origQty”]),
“filled”: float(o[“executedQty”]),
“time”:   o[“time”],
} for o in data]
return {“ok”: True, “orders”: orders}
except Exception as e:
raise HTTPException(500, detail=str(e))

# ─── معلومات رمز معين ────────────────────────────────

@app.get(”/symbol-info/{symbol}”)
async def symbol_info(symbol: str):
try:
data = await binance_get(”/api/v3/exchangeInfo”, {“symbol”: symbol.upper()})
info = data[“symbols”][0]
filters = {f[“filterType”]: f for f in info[“filters”]}
return {
“ok”: True,
“symbol”: info[“symbol”],
“base”: info[“baseAsset”],
“quote”: info[“quoteAsset”],
“status”: info[“status”],
“minQty”:   filters.get(“LOT_SIZE”, {}).get(“minQty”),
“stepSize”: filters.get(“LOT_SIZE”, {}).get(“stepSize”),
“minNotional”: filters.get(“MIN_NOTIONAL”, {}).get(“minNotional”),
“tickSize”: filters.get(“PRICE_FILTER”, {}).get(“tickSize”),
}
except Exception as e:
raise HTTPException(500, detail=str(e))

# ─── تشغيل الخادم ────────────────────────────────────

if **name** == “**main**”:
import uvicorn
print(”=” * 50)
print(“🚀 بوت التداول - Backend Server”)
print(”=” * 50)
print(“📡 الخادم يعمل على: http://localhost:8000”)
print(“📖 التوثيق:         http://localhost:8000/docs”)
print(”=” * 50)
uvicorn.run(app, host=“0.0.0.0”, port=8000, reload=True)
