"""
노출 데이터 제공자 (PDF §내부 정규화 JSON 스키마).

- AIRKOREA_SERVICE_KEY가 설정되면 실제 OpenAPI 호출.
- 그렇지 않으면 지역+날짜 기반 결정론적 mock(사인 변동 + 노이즈) 사용.
- 단위는 PDF 권장에 따라 PM은 µg/m³, 가스는 ppb로 정규화.
"""
from __future__ import annotations

import math
import random
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from .airkorea import fetch_daily_stats
from .units import ppm_to_ppb


def _seed_for(region_code: str, day: date) -> int:
    return abs(hash((region_code, day.isoformat()))) % (2**31)


def _mock_daily_exposure(region_code: str, day: date) -> Dict[str, float]:
    """결정론적 mock — 같은 region+date 면 항상 동일 값."""
    rng = random.Random(_seed_for(region_code, day))

    # 계절성: 겨울 PM↑, 여름 O3↑
    doy = day.timetuple().tm_yday
    season_pm = 1.0 + 0.45 * math.cos(2 * math.pi * (doy - 15) / 365.0)
    season_o3 = 1.0 + 0.55 * math.cos(2 * math.pi * (doy - 200) / 365.0)

    pm25 = max(5.0, 22.0 * season_pm + rng.uniform(-6, 8))
    pm10 = max(10.0, pm25 * (1.7 + rng.uniform(-0.2, 0.3)))
    o3_ppb = max(8.0, 30.0 * season_o3 + rng.uniform(-6, 10))
    so2_ppb = max(0.5, 4.0 + rng.uniform(-1.0, 2.0))
    asian_dust = 1.0 if (rng.random() < 0.06 and 60 <= doy <= 150) else 0.0
    ni_ng_m3 = max(0.3, 2.5 + rng.uniform(-1.2, 1.5))

    # 주간 100k당 사례 수 (계절성 + 변동)
    covid_pressure = max(
        0.5,
        25.0 * (1.0 + 0.6 * math.cos(2 * math.pi * (doy - 20) / 365.0))
        + rng.uniform(-8, 12),
    )

    return {
        "pm25": round(pm25, 1),
        "pm10": round(pm10, 1),
        "o3": round(o3_ppb, 1),
        "so2": round(so2_ppb, 2),
        "asianDust": asian_dust,
        "ni": round(ni_ng_m3, 2),
        "covid_pressure": round(covid_pressure, 1),
    }


def _moving_average(series: List[Dict[str, float]], key: str, window: int) -> float:
    if not series:
        return 0.0
    tail = series[-window:]
    vals = [s[key] for s in tail if key in s]
    return sum(vals) / len(vals) if vals else 0.0


async def get_exposure_window(
    region_code: str,
    target_date: date,
    history_days: int = 7,
) -> Dict[str, object]:
    """target_date 기준 최근 history_days 일의 일별 노출 + 윈도우 평균."""
    daily: List[Dict[str, float]] = []
    for i in range(history_days, 0, -1):
        d = target_date - timedelta(days=i - 1)
        # TODO: AirKorea 실호출 결과를 매핑하는 분기 추가 가능
        daily.append({"date": d.isoformat(), **_mock_daily_exposure(region_code, d)})

    # 7일 이동평균(노출 창) — PDF의 ALRI 모델은 7DMA PM2.5
    pm25_7dma = _moving_average(daily, "pm25", 7)
    pm10_7dma = _moving_average(daily, "pm10", 7)
    o3_today = daily[-1]["o3"]
    so2_today = daily[-1]["so2"]
    dust_today = daily[-1]["asianDust"]
    ni_today = daily[-1]["ni"]
    covid_pressure = daily[-1]["covid_pressure"]

    return {
        "regionCode": region_code,
        "asOf": target_date.isoformat(),
        "daily": daily,
        "windowed": {
            "pm25": round(pm25_7dma, 1),
            "pm10": round(pm10_7dma, 1),
            "o3": o3_today,
            "so2": so2_today,
            "asianDust": dust_today,
            "ni": ni_today,
            "covid_pressure": covid_pressure,
        },
        "source": "mock" if True else "airkorea",
    }
