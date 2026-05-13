"""
한국환경공단 AirKorea OpenAPI 클라이언트 (PDF §데이터 소스).

운영 시 환경변수 AIRKOREA_SERVICE_KEY 가 설정되면 실제 호출,
없으면 None 을 반환하여 호출부가 mock 으로 fallback 하게 함.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional
from urllib.parse import urlencode

try:
    import httpx  # type: ignore
except ImportError:  # pragma: no cover — optional at runtime
    httpx = None  # type: ignore[assignment]

STATION_LIST_URL = (
    "http://apis.data.go.kr/B552584/MsrstnInfoInqireSvc/getMsrstnList"
)
DAILY_STATS_URL = (
    "http://apis.data.go.kr/B552584/ArpltnStatsSvc/getMsrstnAcctoRDyrg"
)
FORECAST_URL = (
    "http://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getMinuDustFrcstDspth"
)


def _service_key() -> Optional[str]:
    if httpx is None:
        return None
    return '54aa0572e5954a02cfa2b4b05f73e166568c781a450c3213a90ebc3636c1edb1'
    # return os.getenv("AIRKOREA_SERVICE_KEY") or None


async def fetch_stations(addr: Optional[str] = None,
                         num_of_rows: int = 100) -> Optional[Dict[str, Any]]:
    """측정소 목록 조회 (getMsrstnList)."""
    key = _service_key()
    if not key:
        return None
    params = {
        "serviceKey": key,
        "returnType": "json",
        "numOfRows": str(num_of_rows),
        "pageNo": "1",
    }
    if addr:
        params["addr"] = addr
    url = f"{STATION_LIST_URL}?{urlencode(params)}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()


async def fetch_daily_stats(station_name: str,
                            inq_bgin_dt: str,
                            inq_end_dt: str) -> Optional[Dict[str, Any]]:
    """측정소별 일평균 통계 (getMsrstnAcctoRDyrg). 날짜는 YYYYMMDD."""
    key = _service_key()
    if not key:
        return None
    params = {
        "serviceKey": key,
        "returnType": "json",
        "numOfRows": "100",
        "pageNo": "1",
        "msrstnName": station_name,
        "inqBginDt": inq_bgin_dt,
        "inqEndDt": inq_end_dt,
    }
    url = f"{DAILY_STATS_URL}?{urlencode(params)}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()
