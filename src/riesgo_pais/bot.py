"""
Bot de descarga: Riesgo Pais (EMBI) — BCE Ecuador

Fuente: JSON estatico del BCE, actualizado diariamente.
URL   : https://contenido.bce.fin.ec/documentos/informacioneconomica/
        indicadores/general/datos_formulario.json

Estrategia:
  - Descarga directa con requests (no requiere Playwright).
  - Filtra el indicador Riesgo Pais (campo Indicador contiene "Riesgo").
  - Retorna solo registros desde START_DATE hasta hoy.

Tabla destino: riesgo_pais
"""

import json
from datetime import date
from typing import Any

import requests

JSON_URL   = (
    "https://contenido.bce.fin.ec/documentos/informacioneconomica"
    "/indicadores/general/datos_formulario.json"
)
_JSON_KEY  = "view_ind_formulario"
START_DATE = "2017-01-01"
TIMEOUT    = 30  # segundos


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def fetch() -> list[dict]:
    """
    Descarga el JSON del BCE y retorna registros de Riesgo Pais
    desde START_DATE hasta hoy como lista de dicts:
      [{"fecha": date, "valor_riesgo_pais": float, "fecha_actualizacion": date}, ...]
    """
    print("[rp] Descargando datos BCE...")
    raw = _get_json()
    rows = raw.get(_JSON_KEY, [])
    print(f"[rp] Total registros en JSON: {len(rows)}")

    records = []
    today   = date.today().isoformat()
    for row in rows:
        if not _is_riesgo_pais(row):
            continue
        fecha = row.get("Fecha", "")
        if not fecha or fecha < START_DATE or fecha > today:
            continue
        valor = _to_float(row.get("Valor"))
        if valor is None:
            continue
        fecha_act = row.get("Carga", "")
        records.append({
            "fecha":              fecha,
            "valor_riesgo_pais":  valor,
            "fecha_actualizacion": fecha_act or None,
        })

    records.sort(key=lambda r: r["fecha"])
    print(f"[rp] Registros Riesgo Pais desde {START_DATE}: {len(records)}")
    return records


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_json() -> dict[str, Any]:
    resp = requests.get(JSON_URL, timeout=TIMEOUT)
    resp.raise_for_status()
    # Forzar UTF-8 para que la tilde de 'País' se decodifique bien
    return json.loads(resp.content.decode("utf-8"))


def _is_riesgo_pais(row: dict) -> bool:
    indicador = row.get("Indicador", "")
    medida    = row.get("Medida", "")
    # Evita depender de 'ñ' para el filtro
    return "Riesgo" in indicador and "Puntos" in medida


def _to_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return None
