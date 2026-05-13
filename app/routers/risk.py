"""
위험 확률 API 라우터 (PDF §시스템 아키텍처 — POST /v1/risk).

엔드포인트:
- GET  /v1/exposure       : 현재 노출(7DMA + 일별 시계열)
- POST /v1/risk           : 질병별 RR/절대확률(연령·성별 층화 + Monte Carlo CI)
- GET  /v1/risk/timeseries: 최근 N일 절대확률 추이 (어린이/어른 요약)
- GET  /v1/risk/actions   : 질병별 행동요령 (PDF의 그래서 어떻게 할지)
- GET  /v1/diseases       : 지원 질병 ID 목록
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..risk.baseline import AGE_GROUPS, SEXES, get_lambda0
from ..risk.effects import DISEASE_EFFECTS, get_effects
from ..risk.exposure import get_exposure_window
from ..risk.math_core import absolute_prob_from_hazard, rr_from_effects
from ..risk.monte_carlo import monte_carlo_ci

router = APIRouter(prefix="/v1/risk", tags=["risk"])


# ── 행동요령(질병별) ─────────────────────────────────────────────
DISEASE_ACTIONS: Dict[str, Dict[str, List[str]]] = {
    "covid": {
        "child": ["마스크 착용", "손 씻기", "사람 많은 곳 피하기", "증상 있으면 병원 방문"],
        "adult": ["KF94 마스크", "환기 자주", "백신 접종 확인", "증상 시 신속검사"],
        "common": ["실내 공기청정기 사용", "외출 후 손 씻기", "충분한 수면", "물 자주 마시기"],
    },
    "cold": {
        "child": ["체온 자주 확인", "충분한 수분 섭취", "따뜻하게 유지", "푹 쉬기"],
        "adult": ["충분한 수면", "비타민 섭취", "외출 후 손 씻기", "증상 시 병원 방문"],
        "common": ["실내 적정 습도", "환기", "손 씻기", "사람 많은 곳 피하기"],
    },
    "flu": {
        "child": ["독감 예방접종 확인", "마스크 착용", "사람 많은 곳 피하기", "발열 시 즉시 병원"],
        "adult": ["독감 예방접종", "충분한 휴식", "수분 섭취", "증상 시 항바이러스제 상담"],
        "common": ["손 씻기", "기침 예절", "환기", "균형 잡힌 식사"],
    },
    "pneumonia": {
        "child": ["체온 모니터링", "기침/호흡곤란 시 병원", "예방접종 확인", "충분한 수분"],
        "adult": ["폐렴구균 백신 확인", "금연", "기저질환 관리", "고열·호흡곤란 시 즉시 병원"],
        "common": ["미세먼지 마스크", "외출 자제", "공기청정기", "면역력 관리"],
    },
    "allergy": {
        "child": ["꽃가루 노출 줄이기", "외출 후 샤워", "침구 자주 세탁", "처방약 정시 복용"],
        "adult": ["항히스타민제 준비", "황사 예보 확인", "공기청정기 가동", "증상 악화 시 진료"],
        "common": ["실내 환기 시간 조절", "마스크 착용", "건조 방지", "알레르겐 차단"],
    },
}


# ── 요청/응답 스키마 ─────────────────────────────────────────────
class RiskRequest(BaseModel):
    disease: Literal["covid", "cold", "flu", "pneumonia", "allergy"]
    region_code: str = Field(default="11", description="시도 코드 또는 시군구 코드")
    target_date: Optional[str] = Field(default=None, description="YYYY-MM-DD; 없으면 오늘")
    horizon_days: int = Field(default=1, ge=1, le=30)
    mc_samples: int = Field(default=2000, ge=200, le=20000)
    

class StratumResult(BaseModel):
    age_group: str
    sex: str
    rr: float
    probability: float
    ci: Dict[str, Dict[str, float]]
    lambda0_per_day: float


class RiskResponse(BaseModel):
    disease: str
    region_code: str
    target_date: str
    horizon_days: int
    exposures: Dict[str, float]
    summary: Dict[str, Dict[str, float]]  # child/adult: {probability, rr}
    results: List[StratumResult]


# ── 유틸 ────────────────────────────────────────────────────────
def _parse_date(s: Optional[str]) -> date:
    if not s:
        return date.today()
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(400, f"Invalid date: {s}") from exc


def _summarize(results: List[StratumResult]) -> Dict[str, Dict[str, float]]:
    """
    프론트는 어린이(<12) / 어른(≥12)로 표시 → 가중치 평균(노출 인구 가정 동일).
    어린이: 0-4, 5-17 / 어른: 18-49, 50-64, 65+
    """
    child_groups = {"0-4", "5-17"}
    adult_groups = {"18-49", "50-64", "65+"}

    def avg(groups: set) -> Dict[str, float]:
        rows = [r for r in results if r.age_group in groups]
        if not rows:
            return {"probability": 0.0, "rr": 1.0}
        return {
            "probability": sum(r.probability for r in rows) / len(rows),
            "rr": sum(r.rr for r in rows) / len(rows),
        }

    return {"child": avg(child_groups), "adult": avg(adult_groups)}


# ── 엔드포인트 ──────────────────────────────────────────────────
@router.get("/diseases")
def list_diseases():
    return {
        "diseases": [
            {"id": d, "effectCount": len(effects)}
            for d, effects in DISEASE_EFFECTS.items()
        ]
    }


@router.get("/exposure")
async def get_exposure(
    region_code: str = Query("11"),
    target_date: Optional[str] = Query(None),
    history_days: int = Query(7, ge=1, le=30),
):
    d = _parse_date(target_date)
    return await get_exposure_window(region_code, d, history_days)


@router.post("/risk", response_model=RiskResponse)
async def compute_risk(req: RiskRequest):
    if req.disease not in DISEASE_EFFECTS:
        raise HTTPException(400, f"Unknown disease: {req.disease}")

    target = _parse_date(req.target_date)
    exposure = await get_exposure_window(req.region_code, target, history_days=7)
    windowed: Dict[str, float] = exposure["windowed"]  # type: ignore[assignment]
    

    effects = get_effects(req.disease)

    results: List[StratumResult] = []
    for ag in AGE_GROUPS:
        for sx in SEXES:
            lambda0 = get_lambda0(req.disease, ag, sx)
            rr = rr_from_effects(effects, windowed)
            p = absolute_prob_from_hazard(lambda0, rr, req.horizon_days)
            ci = monte_carlo_ci(
                effects=effects,
                exposures=windowed,
                lambda0_per_day=lambda0,
                delta_t_days=req.horizon_days,
                n=req.mc_samples,
                seed=hash((req.disease, ag, sx, req.region_code, target.toordinal()))
                & 0x7FFFFFFF,
            )
            results.append(
                StratumResult(
                    age_group=ag,
                    sex=sx,
                    rr=rr,
                    probability=p,
                    ci=ci,
                    lambda0_per_day=lambda0,
                )
            )

    return RiskResponse(
        disease=req.disease,
        region_code=req.region_code,
        target_date=target.isoformat(),
        horizon_days=req.horizon_days,
        exposures=windowed,
        summary=_summarize(results),
        results=results,
    )


@router.get("/risk/timeseries")
async def risk_timeseries(
    disease: str = Query(...),
    region_code: str = Query("11"),
    days: int = Query(5, ge=2, le=30),
):
    """최근 days 일의 어린이/어른 절대확률 추이."""
    if disease not in DISEASE_EFFECTS:
        raise HTTPException(400, f"Unknown disease: {disease}")
    effects = get_effects(disease)
    today = date.today()

    points = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        exposure = await get_exposure_window(region_code, d, history_days=7)
        w = exposure["windowed"]

        rr = rr_from_effects(effects, w)
        # 단순화: 어린이/어른 각각 한 stratum 대표값으로 평균 (5세 남, 30대 남)
        p_child = absolute_prob_from_hazard(get_lambda0(disease, "0-4", "male"), rr, 1)
        p_adult = absolute_prob_from_hazard(
            get_lambda0(disease, "18-49", "male"), rr, 1
        )
        points.append(
            {
                "date": d.strftime("%m/%d"),
                "iso": d.isoformat(),
                "child": round(p_child * 100, 2),
                "adult": round(p_adult * 100, 2),
                "rr": round(rr, 4),
            }
        )

    return {
        "disease": disease,
        "region_code": region_code,
        "points": points,
    }


@router.get("/risk/actions")
def risk_actions(disease: str = Query(...)):
    if disease not in DISEASE_ACTIONS:
        raise HTTPException(400, f"Unknown disease: {disease}")
    return {"disease": disease, **DISEASE_ACTIONS[disease]}
