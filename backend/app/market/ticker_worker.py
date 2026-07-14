"""Real-time market ticker worker.

Fetches live prices and intraday chart history from Yahoo Finance every 30-60
seconds. Uses an optional random-walk fallback only when MARKET_ALLOW_SIMULATION=true.
Production defaults to preserving the last confirmed quote instead of inventing data.
"""
import json
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import requests

from app.config import get_settings
from app.database import SessionLocal
from app.models import MarketTicker

logger = logging.getLogger("slayz.market")
settings = get_settings()

# Core tickers. "seed" is used only for first-time simulation fallback.
TICKER_SYMBOLS = [
    # BIST Indices
    {"symbol": "XU100", "name": "BIST 100", "category": "index", "currency": "TRY", "seed": 14000.0},
    {"symbol": "XU030", "name": "BIST 30", "category": "index", "currency": "TRY", "seed": 4500.0},
    # BIST 100 Equities
    {"symbol": "AEFES", "name": "Anadolu Efes", "category": "equity", "currency": "TRY", "seed": 65.0},
    {"symbol": "AKBNK", "name": "Akbank", "category": "equity", "currency": "TRY", "seed": 55.0},
    {"symbol": "AKSA", "name": "Aksa Akrilik", "category": "equity", "currency": "TRY", "seed": 45.0},
    {"symbol": "AKSEN", "name": "Aksa Enerji", "category": "equity", "currency": "TRY", "seed": 35.0},
    {"symbol": "ALARK", "name": "Alarko Holding", "category": "equity", "currency": "TRY", "seed": 25.0},
    {"symbol": "ALTNY", "name": "Altınay", "category": "equity", "currency": "TRY", "seed": 30.0},
    {"symbol": "ANSGR", "name": "Anadolu Sigorta", "category": "equity", "currency": "TRY", "seed": 40.0},
    {"symbol": "ARCLK", "name": "Arçelik", "category": "equity", "currency": "TRY", "seed": 85.0},
    {"symbol": "ASELS", "name": "Aselsan", "category": "equity", "currency": "TRY", "seed": 85.0},
    {"symbol": "ASTOR", "name": "Astor Enerji", "category": "equity", "currency": "TRY", "seed": 20.0},
    {"symbol": "BALSU", "name": "Balsu Gıda", "category": "equity", "currency": "TRY", "seed": 35.0},
    {"symbol": "BERA", "name": "Bera Holding", "category": "equity", "currency": "TRY", "seed": 45.0},
    {"symbol": "BIMAS", "name": "Bim", "category": "equity", "currency": "TRY", "seed": 150.0},
    {"symbol": "BRSAN", "name": "Borusan Boru", "category": "equity", "currency": "TRY", "seed": 40.0},
    {"symbol": "BRYAT", "name": "Borusan Yatırım", "category": "equity", "currency": "TRY", "seed": 25.0},
    {"symbol": "BSOKE", "name": "Batısöke Çimento", "category": "equity", "currency": "TRY", "seed": 30.0},
    {"symbol": "BTCIM", "name": "Batıçim", "category": "equity", "currency": "TRY", "seed": 35.0},
    {"symbol": "CANTE", "name": "Çan2 Termik", "category": "equity", "currency": "TRY", "seed": 20.0},
    {"symbol": "CCOLA", "name": "Coca Cola İçecek", "category": "equity", "currency": "TRY", "seed": 120.0},
    {"symbol": "CIMSA", "name": "Çimsa", "category": "equity", "currency": "TRY", "seed": 45.0},
    {"symbol": "CVKMD", "name": "Çvk Maden", "category": "equity", "currency": "TRY", "seed": 30.0},
    {"symbol": "CWENE", "name": "CW Enerji", "category": "equity", "currency": "TRY", "seed": 25.0},
    {"symbol": "DAPGM", "name": "Dap Gayrimenkul", "category": "equity", "currency": "TRY", "seed": 15.0},
    {"symbol": "DOAS", "name": "Doğuş Otomotiv", "category": "equity", "currency": "TRY", "seed": 20.0},
    {"symbol": "DOHOL", "name": "Doğan Holding", "category": "equity", "currency": "TRY", "seed": 25.0},
    {"symbol": "DSTKF", "name": "Destek Finans", "category": "equity", "currency": "TRY", "seed": 15.0},
    {"symbol": "ECILC", "name": "Eczacıbaşı İlaç", "category": "equity", "currency": "TRY", "seed": 100.0},
    {"symbol": "EFOR", "name": "Efor Yatırım", "category": "equity", "currency": "TRY", "seed": 20.0},
    {"symbol": "EKGYO", "name": "Emlak Konut GYO", "category": "equity", "currency": "TRY", "seed": 35.0},
    {"symbol": "ENERY", "name": "Enerya Enerji", "category": "equity", "currency": "TRY", "seed": 25.0},
    {"symbol": "ENJSA", "name": "Enerjisa Enerji", "category": "equity", "currency": "TRY", "seed": 45.0},
    {"symbol": "ENKAI", "name": "Enka İnşaat", "category": "equity", "currency": "TRY", "seed": 35.0},
    {"symbol": "EREGL", "name": "Ereğli Demir Çelik", "category": "equity", "currency": "TRY", "seed": 44.0},
    {"symbol": "ESEN", "name": "Esenboga Elektrik", "category": "equity", "currency": "TRY", "seed": 20.0},
    {"symbol": "EUPWR", "name": "Europower Enerji", "category": "equity", "currency": "TRY", "seed": 25.0},
    {"symbol": "EUREN", "name": "Europen Endustri", "category": "equity", "currency": "TRY", "seed": 20.0},
    {"symbol": "FENER", "name": "Fenerbahçe", "category": "equity", "currency": "TRY", "seed": 50.0},
    {"symbol": "FROTO", "name": "Ford Otosan", "category": "equity", "currency": "TRY", "seed": 650.0},
    {"symbol": "GARAN", "name": "Garanti BBVA", "category": "equity", "currency": "TRY", "seed": 45.0},
    {"symbol": "GENIL", "name": "Gen İlaç", "category": "equity", "currency": "TRY", "seed": 30.0},
    {"symbol": "GESAN", "name": "Girişim Elektrik", "category": "equity", "currency": "TRY", "seed": 25.0},
    {"symbol": "GLRMK", "name": "Gülermak", "category": "equity", "currency": "TRY", "seed": 20.0},
    {"symbol": "GRSEL", "name": "Gürsel Turizm", "category": "equity", "currency": "TRY", "seed": 15.0},
    {"symbol": "GRTHO", "name": "Grainturk Holding", "category": "equity", "currency": "TRY", "seed": 20.0},
    {"symbol": "GSRAY", "name": "Galatasaray Sportif", "category": "equity", "currency": "TRY", "seed": 25.0},
    {"symbol": "GUBRF", "name": "Gübre Fabrikaları", "category": "equity", "currency": "TRY", "seed": 45.0},
    {"symbol": "HALKB", "name": "Halkbank", "category": "equity", "currency": "TRY", "seed": 35.0},
    {"symbol": "HEKTS", "name": "Hektaş", "category": "equity", "currency": "TRY", "seed": 40.0},
    {"symbol": "IEYHO", "name": "Işıklar Enerji Yapı Holding", "category": "equity", "currency": "TRY", "seed": 20.0},
    {"symbol": "IPEKE", "name": "İpek Doğal Enerji", "category": "equity", "currency": "TRY", "seed": 25.0},
    {"symbol": "ISCTR", "name": "İş Bankası", "category": "equity", "currency": "TRY", "seed": 50.0},
    {"symbol": "ISMEN", "name": "İş Yatırım", "category": "equity", "currency": "TRY", "seed": 30.0},
    {"symbol": "IZENR", "name": "İzdemir Enerji", "category": "equity", "currency": "TRY", "seed": 20.0},
    {"symbol": "KCHOL", "name": "Koç Holding", "category": "equity", "currency": "TRY", "seed": 75.0},
    {"symbol": "KLRHO", "name": "Kiler Holding", "category": "equity", "currency": "TRY", "seed": 15.0},
    {"symbol": "KRDMD", "name": "Kardemir", "category": "equity", "currency": "TRY", "seed": 15.0},
    {"symbol": "KTLEV", "name": "Katılımevim", "category": "equity", "currency": "TRY", "seed": 20.0},
    {"symbol": "KUYAS", "name": "Kuyas Yatırım", "category": "equity", "currency": "TRY", "seed": 15.0},
    {"symbol": "MAGEN", "name": "Magen", "category": "equity", "currency": "TRY", "seed": 20.0},
    {"symbol": "MAVI", "name": "Mavi Giyim", "category": "equity", "currency": "TRY", "seed": 100.0},
    {"symbol": "MGROS", "name": "Migros", "category": "equity", "currency": "TRY", "seed": 90.0},
    {"symbol": "MIATK", "name": "Mia Teknoloji", "category": "equity", "currency": "TRY", "seed": 30.0},
    {"symbol": "MPARK", "name": "Mlp Sağlık", "category": "equity", "currency": "TRY", "seed": 25.0},
    {"symbol": "OBAMS", "name": "Oba Makarna", "category": "equity", "currency": "TRY", "seed": 20.0},
    {"symbol": "ODAS", "name": "Odas Elektrik", "category": "equity", "currency": "TRY", "seed": 25.0},
    {"symbol": "ODINE", "name": "Odine Solutions", "category": "equity", "currency": "TRY", "seed": 20.0},
    {"symbol": "OTKAR", "name": "Otokar", "category": "equity", "currency": "TRY", "seed": 450.0},
    {"symbol": "OYAKC", "name": "Oyak Çimento", "category": "equity", "currency": "TRY", "seed": 35.0},
    {"symbol": "PAHOL", "name": "Pasifik Gayrimenkul", "category": "equity", "currency": "TRY", "seed": 15.0},
    {"symbol": "PASEU", "name": "Pasifik Eurasia", "category": "equity", "currency": "TRY", "seed": 15.0},
    {"symbol": "PATEK", "name": "Pasifik Teknoloji", "category": "equity", "currency": "TRY", "seed": 20.0},
    {"symbol": "PETKM", "name": "Petkim", "category": "equity", "currency": "TRY", "seed": 40.0},
    {"symbol": "PGSUS", "name": "Pegasus", "category": "equity", "currency": "TRY", "seed": 150.0},
    {"symbol": "PSGYO", "name": "Pasifik Gayrimenkul", "category": "equity", "currency": "TRY", "seed": 15.0},
    {"symbol": "QUAGR", "name": "Qua Granite", "category": "equity", "currency": "TRY", "seed": 20.0},
    {"symbol": "RALYH", "name": "Ral Yatırım", "category": "equity", "currency": "TRY", "seed": 15.0},
    {"symbol": "REEDR", "name": "Reeder Teknoloji", "category": "equity", "currency": "TRY", "seed": 25.0},
    {"symbol": "SAHOL", "name": "Sabancı Holding", "category": "equity", "currency": "TRY", "seed": 25.0},
    {"symbol": "SARKY", "name": "Sarkuysan", "category": "equity", "currency": "TRY", "seed": 35.0},
    {"symbol": "SASA", "name": "Sasa Polyester", "category": "equity", "currency": "TRY", "seed": 35.0},
    {"symbol": "SISE", "name": "Şişecam", "category": "equity", "currency": "TRY", "seed": 55.0},
    {"symbol": "SKBNK", "name": "Şekerbank", "category": "equity", "currency": "TRY", "seed": 15.0},
    {"symbol": "SOKM", "name": "Sok Marketler", "category": "equity", "currency": "TRY", "seed": 50.0},
    {"symbol": "TAVHL", "name": "TAV Havalimanları", "category": "equity", "currency": "TRY", "seed": 100.0},
    {"symbol": "TCELL", "name": "Turkcell", "category": "equity", "currency": "TRY", "seed": 45.0},
    {"symbol": "THYAO", "name": "Türk Hava Yolları", "category": "equity", "currency": "TRY", "seed": 285.0},
    {"symbol": "TKFEN", "name": "Tekfen Holding", "category": "equity", "currency": "TRY", "seed": 45.0},
    {"symbol": "TOASO", "name": "Tofaş", "category": "equity", "currency": "TRY", "seed": 250.0},
    {"symbol": "TRALT", "name": "Türk Altın", "category": "equity", "currency": "TRY", "seed": 25.0},
    {"symbol": "TRENJ", "name": "Tren Enerji", "category": "equity", "currency": "TRY", "seed": 20.0},
    # Gold Mining Stocks
    {"symbol": "KOZAL", "name": "Koza Altın", "category": "equity", "currency": "TRY", "seed": 45.0},
    {"symbol": "KOZAA", "name": "Koza Anadolu Metal", "category": "equity", "currency": "TRY", "seed": 35.0},
    {"symbol": "PRKME", "name": "Park Elektrik Madencilik", "category": "equity", "currency": "TRY", "seed": 15.0},
    {"symbol": "MARBL", "name": "Tureks Turunç Madencilik", "category": "equity", "currency": "TRY", "seed": 20.0},
    {"symbol": "VSNMD", "name": "Vişne Madencilik", "category": "equity", "currency": "TRY", "seed": 15.0},
    {"symbol": "RUZYE", "name": "Ruzy Madencilik", "category": "equity", "currency": "TRY", "seed": 10.0},
    {"symbol": "TSKB", "name": "TSKB", "category": "equity", "currency": "TRY", "seed": 40.0},
    {"symbol": "TTKOM", "name": "Türk Telekom", "category": "equity", "currency": "TRY", "seed": 15.0},
    {"symbol": "TUKAS", "name": "Tukas Gıda", "category": "equity", "currency": "TRY", "seed": 25.0},
    {"symbol": "TUPRS", "name": "Tüpraş", "category": "equity", "currency": "TRY", "seed": 550.0},
    {"symbol": "TURSG", "name": "Türkiye Sigorta", "category": "equity", "currency": "TRY", "seed": 20.0},
    {"symbol": "ULKER", "name": "Ülker Bisküvi", "category": "equity", "currency": "TRY", "seed": 200.0},
    {"symbol": "VAKBN", "name": "Vakıfbank", "category": "equity", "currency": "TRY", "seed": 35.0},
    {"symbol": "VESTL", "name": "Vestel", "category": "equity", "currency": "TRY", "seed": 25.0},
    {"symbol": "YKBNK", "name": "Yapı Kredi", "category": "equity", "currency": "TRY", "seed": 40.0},
    {"symbol": "ZOREN", "name": "Zorlu Enerji", "category": "equity", "currency": "TRY", "seed": 35.0},
    # Forex Pairs
    {"symbol": "USDTRY", "name": "Dolar / TL", "category": "forex", "currency": "TRY", "seed": 32.5},
    {"symbol": "EURTRY", "name": "Euro / TL", "category": "forex", "currency": "TRY", "seed": 35.0},
    {"symbol": "GBPTRY", "name": "Sterlin / TL", "category": "forex", "currency": "TRY", "seed": 41.0},
    {"symbol": "EURUSD", "name": "Euro / Dolar", "category": "forex", "currency": "USD", "seed": 1.08},
    # Commodities
    {"symbol": "XAUUSD", "name": "Altın Ons", "category": "commodity", "currency": "USD", "seed": 2350.0},
    {"symbol": "GRAMALTIN", "name": "Gram Altın", "category": "commodity", "currency": "TRY", "seed": 1850.0},
    {"symbol": "XAGUSD", "name": "Gümüş Ons", "category": "commodity", "currency": "USD", "seed": 28.0},
    {"symbol": "BRENT", "name": "Brent Petrol", "category": "commodity", "currency": "USD", "seed": 85.0},
    # Crypto
    {"symbol": "BTCUSD", "name": "Bitcoin / USD", "category": "crypto", "currency": "USD", "seed": 68000.0},
    {"symbol": "ETHUSD", "name": "Ethereum / USD", "category": "crypto", "currency": "USD", "seed": 3500.0},
    {"symbol": "SOLUSD", "name": "Solana / USD", "category": "crypto", "currency": "USD", "seed": 145.0},
    {"symbol": "BNBUSD", "name": "BNB / USD", "category": "crypto", "currency": "USD", "seed": 590.0},
]

# Yahoo Finance symbols for direct price lookups.
# Gold is sourced from GLD (a physical-gold ETF; 1 share ≈ 0.1 troy oz) and
# converted back to a per-ounce spot price so the terminal shows a realistic,
# market-driven XAU/USD value instead of a far-dated futures contract.
YAHOO_SYMBOL_MAP = {
    # BIST Indices
    "XU100": "XU100.IS",
    "XU030": "XU030.IS",
    # BIST Equities
    "AEFES": "AEFES.IS",
    "AKBNK": "AKBNK.IS",
    "AKSA": "AKSA.IS",
    "AKSEN": "AKSEN.IS",
    "ALARK": "ALARK.IS",
    "ALTNY": "ALTNY.IS",
    "ANSGR": "ANSGR.IS",
    "ARCLK": "ARCLK.IS",
    "ASELS": "ASELS.IS",
    "ASTOR": "ASTOR.IS",
    "BALSU": "BALSU.IS",
    "BERA": "BERA.IS",
    "BIMAS": "BIMAS.IS",
    "BRSAN": "BRSAN.IS",
    "BRYAT": "BRYAT.IS",
    "BSOKE": "BSOKE.IS",
    "BTCIM": "BTCIM.IS",
    "CANTE": "CANTE.IS",
    "CCOLA": "CCOLA.IS",
    "CIMSA": "CIMSA.IS",
    "CVKMD": "CVKMD.IS",
    "CWENE": "CWENE.IS",
    "DAPGM": "DAPGM.IS",
    "DOAS": "DOAS.IS",
    "DOHOL": "DOHOL.IS",
    "DSTKF": "DSTKF.IS",
    "ECILC": "ECILC.IS",
    "EFOR": "EFOR.IS",
    "EKGYO": "EKGYO.IS",
    "ENERY": "ENERY.IS",
    "ENJSA": "ENJSA.IS",
    "ENKAI": "ENKAI.IS",
    "EREGL": "EREGL.IS",
    "ESEN": "ESEN.IS",
    "EUPWR": "EUPWR.IS",
    "EUREN": "EUREN.IS",
    "FENER": "FENER.IS",
    "FROTO": "FROTO.IS",
    "GARAN": "GARAN.IS",
    "GENIL": "GENIL.IS",
    "GESAN": "GESAN.IS",
    "GLRMK": "GLRMK.IS",
    "GRSEL": "GRSEL.IS",
    "GRTHO": "GRTHO.IS",
    "GSRAY": "GSRAY.IS",
    "GUBRF": "GUBRF.IS",
    "HALKB": "HALKB.IS",
    "HEKTS": "HEKTS.IS",
    "IEYHO": "IEYHO.IS",
    "IPEKE": "IPEKE.IS",
    "ISCTR": "ISCTR.IS",
    "ISMEN": "ISMEN.IS",
    "IZENR": "IZENR.IS",
    "KCHOL": "KCHOL.IS",
    "KLRHO": "KLRHO.IS",
    "KRDMD": "KRDMD.IS",
    "KTLEV": "KTLEV.IS",
    "KUYAS": "KUYAS.IS",
    "MAGEN": "MAGEN.IS",
    "MAVI": "MAVI.IS",
    "MGROS": "MGROS.IS",
    "MIATK": "MIATK.IS",
    "MPARK": "MPARK.IS",
    "OBAMS": "OBAMS.IS",
    "ODAS": "ODAS.IS",
    "ODINE": "ODINE.IS",
    "OTKAR": "OTKAR.IS",
    "OYAKC": "OYAKC.IS",
    "PAHOL": "PAHOL.IS",
    "PASEU": "PASEU.IS",
    "PATEK": "PATEK.IS",
    "PETKM": "PETKM.IS",
    "PGSUS": "PGSUS.IS",
    "PSGYO": "PSGYO.IS",
    "QUAGR": "QUAGR.IS",
    "RALYH": "RALYH.IS",
    "REEDR": "REEDR.IS",
    "SAHOL": "SAHOL.IS",
    "SARKY": "SARKY.IS",
    "SASA": "SASA.IS",
    "SISE": "SISE.IS",
    "SKBNK": "SKBNK.IS",
    "SOKM": "SOKM.IS",
    "TAVHL": "TAVHL.IS",
    "TCELL": "TCELL.IS",
    "THYAO": "THYAO.IS",
    "TKFEN": "TKFEN.IS",
    "TOASO": "TOASO.IS",
    "TRALT": "TRALT.IS",
    "TRENJ": "TRENJ.IS",
    "TRMET": "TRMET.IS",
    # Gold Mining Stocks
    "KOZAL": "KOZAL.IS",
    "KOZAA": "KOZAA.IS",
    "PRKME": "PRKME.IS",
    "MARBL": "MARBL.IS",
    "VSNMD": "VSNMD.IS",
    "RUZYE": "RUZYE.IS",
    "TSKB": "TSKB.IS",
    "TTKOM": "TTKOM.IS",
    "TUKAS": "TUKAS.IS",
    "TUPRS": "TUPRS.IS",
    "TURSG": "TURSG.IS",
    "ULKER": "ULKER.IS",
    "VAKBN": "VAKBN.IS",
    "VESTL": "VESTL.IS",
    "YKBNK": "YKBNK.IS",
    "ZOREN": "ZOREN.IS",
    # Forex Pairs
    "USDTRY": "USDTRY=X",
    "EURTRY": "EURTRY=X",
    "GBPTRY": "GBPTRY=X",
    "EURUSD": "EURUSD=X",
    # Commodities
    "XAUUSD": "GLD",       # GLD ETF, converted to per-oz spot
    "XAGUSD": "SI=F",      # Silver futures
    "BRENT": "BZ=F",       # Brent crude futures
    # Crypto
    "BTCUSD": "BTC-USD",
    "ETHUSD": "ETH-USD",
    "SOLUSD": "SOL-USD",
    "BNBUSD": "BNB-USD",
}


def _yahoo_symbol(symbol: str) -> str:
    return YAHOO_SYMBOL_MAP.get(symbol, symbol)


def _yahoo_chart(symbol: str, range_: str = "1d", interval: str = "5m") -> Optional[Dict]:
    """Fetch full chart data from Yahoo Finance: timestamps, closes, meta."""
    ysym = _yahoo_symbol(symbol)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ysym}"
    try:
        resp = requests.get(
            url,
            params={"range": range_, "interval": interval},
            headers={"User-Agent": settings.scraper_user_agent},
            timeout=12,
        )
        resp.raise_for_status()
        data = resp.json()
        result = data.get("chart", {}).get("result", [None])[0]
        if not result:
            return None
        return result
    except Exception as exc:
        logger.debug("Yahoo chart fetch failed for %s: %s", symbol, exc)
        return None


def _extract_latest(result: Dict) -> Optional[Dict[str, float]]:
    meta = result.get("meta", {})
    prices = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
    if not prices:
        return None
    latest = next((p for p in reversed(prices) if p is not None), None)
    if latest is None:
        return None
    prev_close = meta.get("previousClose") or meta.get("chartPreviousClose") or latest
    change = latest - prev_close
    change_pct = (change / prev_close) * 100 if prev_close else 0.0
    return {"price": latest, "change": change, "change_percent": change_pct}


def _extract_history(result: Dict) -> List[List[float]]:
    timestamps = result.get("timestamp", [])
    prices = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
    history = []
    for ts, price in zip(timestamps, prices):
        if price is not None and ts is not None:
            history.append([float(ts), round(float(price), 4)])
    return history


def _fetch_yahoo_usdtry() -> Optional[float]:
    """Fetch USD/TRY rate; needed for gram gold calculation."""
    result = _yahoo_chart("USDTRY=X", range_="1d", interval="5m")
    if not result:
        return None
    latest = _extract_latest(result)
    return latest["price"] if latest else None


def _fetch_yahoo_xauusd() -> Tuple[Optional[float], List[List[float]]]:
    """Fetch gold price per troy ounce and its intraday history."""
    result = _yahoo_chart("XAUUSD", range_="1d", interval="5m")
    if not result:
        return None, []
    latest = _extract_latest(result)
    history = _extract_history(result)
    return (latest["price"] if latest else None), history


def _calculate_gram_altin(xauusd: float, usdtry: float) -> float:
    """1 troy ounce = 31.1034768 grams. Convert USD/oz to TRY/gram."""
    return (xauusd * usdtry) / 31.1034768


def _simulate_tick(symbol: str, seed: float, history: List[List[float]]) -> Dict[str, float]:
    """Realistic random-walk simulation; stays close to the last known price."""
    last = history[-1][1] if history else seed
    # Adjust volatility by category for more realistic simulation.
    if symbol in ("BTCUSD", "ETHUSD", "SOLUSD", "BNBUSD"):
        volatility = 0.02
    elif symbol in ("XAUUSD", "XAGUSD", "GRAMALTIN", "BRENT"):
        volatility = 0.0015
    elif symbol in ("USDTRY", "EURTRY", "GBPTRY", "EURUSD"):
        volatility = 0.0005
    elif symbol.endswith(".IS") or symbol in ("XU100", "XU030"):
        volatility = 0.003
    else:
        volatility = 0.0025
    change = last * random.uniform(-volatility, volatility)
    new_price = max(0.01, last + change)
    change_pct = (change / last) * 100 if last else 0.0
    return {"price": new_price, "change": change, "change_percent": change_pct}


def _get_or_create_ticker(db, meta: Dict[str, any]) -> MarketTicker:
    ticker = db.query(MarketTicker).filter(MarketTicker.symbol == meta["symbol"]).first()
    if ticker:
        return ticker
    ticker = MarketTicker(
        symbol=meta["symbol"],
        name=meta["name"],
        category=meta["category"],
        currency=meta["currency"],
    )
    db.add(ticker)
    try:
        db.flush()
    except Exception:
        db.rollback()
        ticker = db.query(MarketTicker).filter(MarketTicker.symbol == meta["symbol"]).first()
        if not ticker:
            raise
    return ticker


def _format(value: float) -> str:
    return f"{value:.4f}"


def refresh_tickers() -> List[MarketTicker]:
    """Refresh all configured tickers from real Yahoo data with full history."""
    db = SessionLocal()
    updated = []
    try:
        # Shared market inputs for derived tickers.
        usdtry = _fetch_yahoo_usdtry()
        xauusd, xau_history = _fetch_yahoo_xauusd()

        for meta in TICKER_SYMBOLS:
            symbol = meta["symbol"]
            ticker = _get_or_create_ticker(db, meta)
            history = json.loads(ticker.history_json or "[]")
            data: Optional[Dict[str, float]] = None

            if symbol == "GRAMALTIN":
                if xauusd is not None and usdtry is not None:
                    price = _calculate_gram_altin(xauusd, usdtry)
                    # Approximate change from previous stored price or seed.
                    prev = history[-1][1] if history else meta["seed"]
                    change = price - prev
                    change_pct = (change / prev) * 100 if prev else 0.0
                    data = {"price": price, "change": change, "change_percent": change_pct}
                    # Derive gram-altın history from gold history if available.
                    if xau_history and usdtry:
                        history = [[ts, round(_calculate_gram_altin(p, usdtry), 4)] for ts, p in xau_history]
                    ticker.is_simulated = False
                    ticker.source = "yahoo (derived)"
                elif settings.market_allow_simulation:
                    data = _simulate_tick(symbol, meta["seed"], history)
                    ticker.is_simulated = True
                    ticker.source = "simulated"
            else:
                result = _yahoo_chart(symbol, range_="1d", interval="5m")
                if result:
                    latest = _extract_latest(result)
                    if latest:
                        # GLD ETF represents ~0.1 troy oz; convert back to per-oz spot.
                        if symbol == "XAUUSD":
                            latest["price"] *= 10
                            latest["change"] *= 10
                        data = latest
                        history = _extract_history(result)
                        if symbol == "XAUUSD":
                            history = [[ts, round(price * 10, 4)] for ts, price in history]
                        ticker.is_simulated = False
                        ticker.source = "yahoo"
                if data is None and settings.market_allow_simulation:
                    data = _simulate_tick(symbol, meta["seed"], history)
                    ticker.is_simulated = True
                    ticker.source = "simulated"

            if data is None:
                # Keep the last confirmed quote instead of manufacturing a market move.
                ticker.source = "stale" if ticker.price else "unavailable"
                ticker.is_simulated = False
                db.commit()
                continue

            now = datetime.utcnow().timestamp()
            # Append the latest point; keep last 150 points (covers the trading day).
            history.append([now, data["price"]])
            history = history[-150:]

            ticker.price = _format(data["price"])
            ticker.change = _format(data["change"])
            ticker.change_percent = _format(data["change_percent"])
            ticker.history_json = json.dumps(history)
            ticker.last_updated = datetime.utcnow()
            updated.append(ticker)
            db.commit()
    except Exception as exc:
        logger.error("Market ticker refresh failed: %s", exc, exc_info=True)
    finally:
        db.close()
    return updated


def seed_history() -> None:
    """Populate initial history from Yahoo; optional simulation is UI-dev only."""
    db = SessionLocal()
    try:
        usdtry = _fetch_yahoo_usdtry()
        xauusd, xau_history = _fetch_yahoo_xauusd()

        for meta in TICKER_SYMBOLS:
            ticker = _get_or_create_ticker(db, meta)
            if ticker.history_json:
                continue

            if meta["symbol"] == "GRAMALTIN":
                if xauusd is not None and usdtry is not None and xau_history:
                    history = [[ts, round(_calculate_gram_altin(p, usdtry), 4)] for ts, p in xau_history]
                    price = _calculate_gram_altin(xauusd, usdtry)
                    prev = history[0][1] if history else meta["seed"]
                    ticker.price = _format(price)
                    ticker.change = _format(price - prev)
                    ticker.change_percent = _format(((price - prev) / prev) * 100 if prev else 0)
                    ticker.history_json = json.dumps(history)
                    ticker.is_simulated = False
                    ticker.source = "yahoo (derived)"
                    ticker.last_updated = datetime.utcnow()
                    db.commit()
                    continue

            result = _yahoo_chart(meta["symbol"], range_="5d", interval="30m")
            if result:
                history = _extract_history(result)
                latest = _extract_latest(result)
                if latest and history:
                    if meta["symbol"] == "XAUUSD":
                        latest["price"] *= 10
                        latest["change"] *= 10
                        history = [[ts, round(price * 10, 4)] for ts, price in history]
                    ticker.price = _format(latest["price"])
                    ticker.change = _format(latest["change"])
                    ticker.change_percent = _format(latest["change_percent"])
                    ticker.history_json = json.dumps(history)
                    ticker.is_simulated = False
                    ticker.source = "yahoo"
                    ticker.last_updated = datetime.utcnow()
                    db.commit()
                    continue

            if settings.market_allow_simulation:
                # Explicit development-only visual fallback.
                history = []
                price = meta["seed"]
                now = datetime.utcnow()
                for i in range(120, 0, -1):
                    ts = (now - timedelta(seconds=30 * i)).timestamp()
                    price = price * random.uniform(0.9975, 1.0025)
                    history.append([ts, round(price, 4)])
                ticker.history_json = json.dumps(history)
                ticker.price = _format(price)
                ticker.change = "0.0000"
                ticker.change_percent = "0.0000"
                ticker.is_simulated = True
                ticker.source = "simulated"
                ticker.last_updated = now
            else:
                ticker.is_simulated = False
                ticker.source = "unavailable"
            db.commit()
    except Exception as exc:
        logger.error("Market history seeding failed: %s", exc, exc_info=True)
    finally:
        db.close()
