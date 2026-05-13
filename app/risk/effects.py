"""
Effects(노출-반응 계수) 카탈로그.

PDF §노출-반응 계수(β) 예시 테이블을 그대로 코드화.
β = ln(RR_ref) / Δx_ref 로 계산되며, RR_total = exp(Σ β_i · (x_i - xRef_i)).

실제 운영에서는 DB(risk_coefficients 테이블)에 저장하고 모델 버전을 관리해야 함.
여기서는 5개 질병 페이지(코로나·감기·독감·폐렴·알레르기)에 매핑되는 계수 세트를 제공.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Effect:
    name: str            # exposure key: "pm25" | "pm10" | "o3" | "so2" | "asianDust" | "ni" | "covid_pressure"
    beta: float          # log-linear coefficient per unit
    unit: str            # "per_ug_m3" | "per_ppb" | "per_ng_m3" | "binary" | "per_per_100k"
    x_ref: float = 0.0   # reference (counterfactual) level in same units
    se: float = 0.0      # standard error of beta (for Monte Carlo)
    source: str = ""     # citation


def _beta_from_rr(rr: float, delta_x: float) -> float:
    return math.log(rr) / delta_x


def _se_from_ci(rr_lower: float, rr_upper: float, delta_x: float) -> float:
    # SE(β) ≈ (ln(RR_upper) - ln(RR_lower)) / (2 · 1.96)  per the reference Δx
    return (math.log(rr_upper) - math.log(rr_lower)) / (2 * 1.96 * delta_x)


# ── PDF 표 기반 계수 (단위 표준 후) ────────────────────────────────────
# (1) PM2.5 → 0–5세 ALRI 입원, 7일 이동평균, 10 µg/m³당 RR≈1.012 (95% CI 1.0071–1.0171)
PM25_ALRI_BETA = _beta_from_rr(1.012, 10.0)
PM25_ALRI_SE = _se_from_ci(1.20071, 1.0171, 10.0)

# (2) PM2.5 → 소아 천식 ED/입원, 단기 10 µg/m³당 RR=1.048 (1.028–1.067)
PM25_ASTHMA_BETA = _beta_from_rr(1.048, 10.0)
PM25_ASTHMA_SE = _se_from_ci(1.028, 1.067, 10.0)

# (3) PM2.5 → COPD 입원(메타분석) 일평균 10 µg/m³당 RR≈1.016 (1.004–1.029)
PM25_COPD_BETA = _beta_from_rr(1.016, 10.0)
PM25_COPD_SE = _se_from_ci(1.004, 1.029, 10.0)

# (4) O3 → COPD 사망(장기, 한국), 1 ppb당 HR=1.011 (1.008–1.013)
O3_COPD_BETA = _beta_from_rr(1.011, 1.0)
O3_COPD_SE = _se_from_ci(1.008, 1.013, 1.0)

# (5) O3 → 천식 사망(장기, 한국), 1 ppb당 HR=1.016 (1.011–1.022)
O3_ASTHMA_BETA = _beta_from_rr(1.016, 1.0)
O3_ASTHMA_SE = _se_from_ci(1.011, 1.022, 1.0)

# (6) 황사 이벤트 → 천식 병원방문 RR=1.10 (1.01–1.19)
DUST_ASTHMA_BETA = _beta_from_rr(1.10, 1.0)
DUST_ASTHMA_SE = _se_from_ci(1.01, 1.19, 1.0)

# (7) Ni 단기/지연 → 호흡기 사망 RR=1.036 (1.016–1.055) IQR당 (서울 연구 기준)
NI_RESP_BETA_PER_IQR = _beta_from_rr(1.036, 1.0)
NI_RESP_SE_PER_IQR = _se_from_ci(1.016, 1.055, 1.0)

# COVID 유행압력은 PDF에 직접 계수가 없음 — 주간 100k당 100케이스를 RR=2.0 가정의
# 대용 지표(community pressure proxy). 운영 시 표본감시 데이터로 보정 필요.
COVID_PRESSURE_BETA_PER_100K = math.log(2.0) / 100.0
COVID_PRESSURE_SE_PER_100K = (math.log(2.5) - math.log(1.6)) / (2 * 1.96 * 100.0)


# ── 질병별(프론트의 5개 카드와 매핑) Effect 카탈로그 ──────────────────
DISEASE_EFFECTS: Dict[str, List[Effect]] = {
    # 폐렴: ALRI 입원 (Oh et al., 7-day MA PM2.5)
    "pneumonia": [
        Effect("pm25", PM25_ALRI_BETA, "per_ug_m3", x_ref=15.0, se=PM25_ALRI_SE,
               source="Oh et al., 7-day MA PM2.5, ALRI hosp 0–5y"),
        Effect("asianDust", DUST_ASTHMA_BETA * 0.6, "binary", x_ref=0.0,
               se=DUST_ASTHMA_SE * 0.6,
               source="Asian-dust day proxy effect on lower-resp infection"),
    ],

    # 알레르기 (천식 악화 + 황사)
    "allergy": [
        Effect("pm25", PM25_ASTHMA_BETA, "per_ug_m3", x_ref=15.0, se=PM25_ASTHMA_SE,
               source="Pediatric asthma, 10 µg/m³ PM2.5 RR=1.048"),
        Effect("o3", O3_ASTHMA_BETA, "per_ppb", x_ref=30.0, se=O3_ASTHMA_SE,
               source="Korean cohort, asthma mortality, 1 ppb O3 HR=1.016"),
        Effect("asianDust", DUST_ASTHMA_BETA, "binary", x_ref=0.0, se=DUST_ASTHMA_SE,
               source="Chuncheon 2006–2012, asthma ED RR=1.10 on dust days"),
    ],

    # 감기 (URI): PM2.5 단기 + 약한 PM10/SO2 영향. 효과 크기는 천식의 60% 가정.
    "cold": [
        Effect("pm25", PM25_ASTHMA_BETA * 0.6, "per_ug_m3", x_ref=15.0,
               se=PM25_ASTHMA_SE * 0.6,
               source="URI proxy: 60% of pediatric asthma PM2.5 effect"),
        Effect("o3", O3_ASTHMA_BETA * 0.4, "per_ppb", x_ref=30.0,
               se=O3_ASTHMA_SE * 0.4,
               source="URI proxy: 40% of asthma O3 effect"),
    ],

    # 독감 (계절 호흡기 감염): COVID와 유사한 유행압력 베타 + PM2.5 보조
    "flu": [
        Effect("pm25", PM25_ALRI_BETA, "per_ug_m3", x_ref=15.0, se=PM25_ALRI_SE,
               source="Influenza-like illness proxy: ALRI PM2.5 effect"),
        Effect("covid_pressure", COVID_PRESSURE_BETA_PER_100K * 0.6,
               "per_per_100k", x_ref=0.0, se=COVID_PRESSURE_SE_PER_100K * 0.6,
               source="Surveillance pressure proxy (60% of COVID)"),
    ],

    # 코로나: 유행 압력 중심 + PM2.5 단기 보조
    "covid": [
        Effect("covid_pressure", COVID_PRESSURE_BETA_PER_100K, "per_per_100k",
               x_ref=0.0, se=COVID_PRESSURE_SE_PER_100K,
               source="Sentinel surveillance pressure proxy; RR=2.0 per +100/100k"),
        Effect("pm25", PM25_ALRI_BETA * 0.5, "per_ug_m3", x_ref=15.0,
               se=PM25_ALRI_SE * 0.5,
               source="Modest PM2.5 short-term effect on COVID severity proxy"),
    ],
}


def get_effects(disease: str) -> List[Effect]:
    eff = DISEASE_EFFECTS.get(disease)
    if eff is None:
        raise KeyError(f"Unknown disease id: {disease}")
    return eff
