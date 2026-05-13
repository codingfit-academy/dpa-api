"""
기저발생률(λ0, per-day) 테이블 (PDF §절대확률로의 변환 / 기저발생률 필요).

PDF에서 명시적으로 unspecified로 표기된 항목으로, 실제 운영 시
NHIS/HIRA 등에서 (질환·연령·성별·지역·계절) 단위로 산출해야 함.
여기서는 5개 질병 × 5개 연령대 × 성별의 합리적 placeholder를 제공.
"""
from __future__ import annotations

from typing import Dict, Tuple

AgeGroup = str  # "0-4" | "5-17" | "18-49" | "50-64" | "65+"
Sex = str       # "male" | "female"

AGE_GROUPS: Tuple[AgeGroup, ...] = ("0-4", "5-17", "18-49", "50-64", "65+")
SEXES: Tuple[Sex, ...] = ("male", "female")



# disease -> age -> sex -> per-day baseline hazard λ0
# (placeholder, PDF의 unspecified 영역. 운영 시 실측치로 교체할 것)
BASELINE_HAZARD_PER_DAY: Dict[str, Dict[AgeGroup, Dict[Sex, float]]] = {
    "pneumonia": {
        "0-4":   {"male": 0.00045, "female": 0.00040},
        "5-17":  {"male": 0.00012, "female": 0.00010},
        "18-49": {"male": 0.00008, "female": 0.00007},
        "50-64": {"male": 0.00018, "female": 0.00014},
        "65+":   {"male": 0.00060, "female": 0.00045},
    },
    "allergy": {
        "0-4":   {"male": 0.00200, "female": 0.00180},
        "5-17":  {"male": 0.00280, "female": 0.00250},
        "18-49": {"male": 0.00150, "female": 0.00170},
        "50-64": {"male": 0.00100, "female": 0.00120},
        "65+":   {"male": 0.00080, "female": 0.00090},
    },
    "cold": {
        "0-4":   {"male": 0.00800, "female": 0.00750},
        "5-17":  {"male": 0.00500, "female": 0.00500},
        "18-49": {"male": 0.00250, "female": 0.00280},
        "50-64": {"male": 0.00200, "female": 0.00220},
        "65+":   {"male": 0.00280, "female": 0.00260},
    },
    "flu": {
        "0-4":   {"male": 0.00250, "female": 0.00230},
        "5-17":  {"male": 0.00300, "female": 0.00280},
        "18-49": {"male": 0.00150, "female": 0.00160},
        "50-64": {"male": 0.00140, "female": 0.00150},
        "65+":   {"male": 0.00200, "female": 0.00190},
    },
    "covid": {
        "0-4":   {"male": 0.00050, "female": 0.00045},
        "5-17":  {"male": 0.00080, "female": 0.00075},
        "18-49": {"male": 0.00100, "female": 0.00110},
        "50-64": {"male": 0.00110, "female": 0.00100},
        "65+":   {"male": 0.00150, "female": 0.00130},
    },
}


def get_lambda0(disease: str, age_group: AgeGroup, sex: Sex) -> float:
    return BASELINE_HAZARD_PER_DAY[disease][age_group][sex]
