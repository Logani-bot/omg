from __future__ import annotations
import time
import math
import json
import pathlib
from typing import List, Optional

import requests
import pandas as pd
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
BINANCE_BASE = "https://api.binance.com"


class BinanceClient:
    """
    Minimal Binance public client for daily OHLCV.
    - No API key required.
    - Interval fixed to 1d as per project spec (일봉 고정).
    - Timestamps returned as KST-normalized pandas.DatetimeIndex (date only).
    """

    def __init__(self, base_url: str = BINANCE_BASE, session: Optional[requests.Session] = None):
        self.base_url = base_url.rstrip("/")
        self.sess = session or requests.Session()
        self.sess.headers.update({"User-Agent": "phase1.5/0.1"})

    def _get(self, path: str, params: dict | None = None) -> requests.Response:
        url = f"{self.base_url}{path}"
        r = self.sess.get(url, params=params, timeout=20)
        r.raise_for_status()
        return r

    def ticker_24hr(self) -> list[dict]:
        """Return 24hr tickers for all symbols."""
        r = self._get("/api/v3/ticker/24hr")
        return r.json()

    def get_ohlc_daily(self, symbol: str, start: Optional[str] = None, end: Optional[str] = None, limit: int = 1500) -> pd.DataFrame:
        """
        Fetch daily klines for `symbol` from Binance. Returns DataFrame with columns:
        ['date','open','high','low','close','volume']
        - date: datetime64[ns, Asia/Seoul] (normalized to 00:00:00 KST)
        Notes:
          * Binance kline open time is in ms UTC. We shift to KST and drop time.
        """
        params = {
            "symbol": symbol,
            "interval": "1d",
            "limit": min(1500, max(10, limit)),
        }
        # Convert start/end ("YYYY-MM-DD") to ms if provided
        def _to_ms(s: Optional[str]):
            if not s:
                return None
            dt = datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)

        start_ms = _to_ms(start)
        end_ms = _to_ms(end)
        if start_ms:
            params["startTime"] = start_ms
        if end_ms:
            params["endTime"] = end_ms

        r = self._get("/api/v3/klines", params=params)
        raw = r.json()
        if not raw:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"]).astype({
                "open": float, "high": float, "low": float, "close": float, "volume": float
            })

        # columns per kline: [openTime, open, high, low, close, volume, closeTime, ...]
        rows = []
        for k in raw:
            open_ts = int(k[0]) // 1000
            # Shift UTC open time to KST and normalize date
            dt_kst = datetime.fromtimestamp(open_ts, tz=timezone.utc).astimezone(KST)
            
            # 일봉 시작 시간 고려: UTC 00:00 = KST 09:00
            # 한국시간 09:00 이전이면 전날 일봉으로 처리
            if dt_kst.hour < 9:  # 아직 전날 일봉
                date_only = datetime(dt_kst.year, dt_kst.month, dt_kst.day - 1, tzinfo=KST)
            else:  # 오늘 일봉
                date_only = datetime(dt_kst.year, dt_kst.month, dt_kst.day, tzinfo=KST)
            
            rows.append({
                "date": date_only,
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
            })
        df = pd.DataFrame(rows).drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
        return df