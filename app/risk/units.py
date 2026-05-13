"""
가스/PM 단위 변환 (PDF 보고서 §단위 표준화)
- 가스(O3, SO2, NO2, CO): ppb 권장. 외부 데이터가 ppm이면 ×1000.
- PM10/PM2.5: µg/m³.
- 25°C, 1atm 기준 24.45 L/mol.
"""

# Molecular weights (g/mol)
MW = {
    "O3": 48.0,
    "SO2": 64.066,
    "NO2": 46.0055,
    "CO": 28.01,
}


def ppm_to_ppb(ppm: float) -> float:
    return ppm * 1000.0

def ppb_to_ppm(ppb: float) -> float:
    return ppb / 1000.0

def ppb_to_ug_m3(ppb: float, mw_g_mol: float) -> float:
    return (ppb * mw_g_mol) / 24.45


def ug_m3_to_ppb(ug_m3: float, mw_g_mol: float) -> float:
    return (ug_m3 * 24.45) / mw_g_mol
