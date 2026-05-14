"""
Bot de descarga: PIB Per Capita Nominal — BCE Ecuador

Fuente: JSON estatico del BCE (mismo archivo que otros indicadores CNA).
URL   : https://contenido.bce.fin.ec/documentos/informacioneconomica/
        indicadores/real/datos_cna.json

No requiere Playwright — descarga directa con requests.

Filtro: Indicador contiene "PIB Per" y Codigo Variable Dinamica == "val_var10"
Periodicidad: Anual (2000-presente)
Unidad: USD per capita
"""

import json
from datetime import date

import requests

JSON_URL  = (
    "https://contenido.bce.fin.ec/documentos/informacioneconomica"
    "/indicadores/real/datos_cna.json"
)
_JSON_KEY = "view_ind_real_cna"
_VAR_CODE = "val_var10"
TIMEOUT   = 30


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def fetch() -> list[dict]:
    """
    Descarga el JSON BCE y retorna registros de PIB Per Capita Nominal
    como lista de dicts:
      [{"anio": int, "pib_per_capita_usd": float, "fecha_actualizacion": str}, ...]
    """
    print("[pib_pc] Descargando datos BCE...")
    resp = requests.get(JSON_URL, timeout=TIMEOUT)
    resp.raise_for_status()
    data = json.loads(resp.content.decode("utf-8"))

    rows = data.get(_JSON_KEY, [])
    print(f"[pib_pc] Total registros en JSON: {len(rows)}")

    records = []
    for row in rows:
        if not _is_pib_percapita(row):
            continue
        fecha = row.get("Fecha", "")
        if not fecha:
            continue
        try:
            anio = int(fecha[:4])
        except (ValueError, TypeError):
            continue
        valor = _to_float(row.get("Valor"))
        if valor is None:
            continue
        records.append({
            "anio":               anio,
            "pib_per_capita_usd": valor,
            "fecha_actualizacion": (row.get("Carga") or "")[:10] or None,
        })

    records.sort(key=lambda r: r["anio"])
    print(f"[pib_pc] Registros encontrados: {len(records)} ({records[0]['anio']}-{records[-1]['anio']})" if records else "[pib_pc] Sin registros.")
    return records


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_pib_percapita(row: dict) -> bool:
    indicador = row.get("Indicador", "")
    codigo    = row.get("Código Variable Dinámica", "") or row.get("Codigo Variable Dinamica", "")
    return "PIB Per" in indicador and codigo == _VAR_CODE


def _to_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return None
