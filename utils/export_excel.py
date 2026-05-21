"""
Utilidad: Exportar tablas de la BD a Excel

Lee las tablas existentes en data_verso, permite seleccionarlas
interactivamente y exporta cada una como una hoja en un archivo .xlsx.

Uso CLI:
    python utils/export_excel.py
    python utils/export_excel.py --out reporte.xlsx
    python utils/export_excel.py --out reporte.xlsx --limit 5000

Uso programatico:
    from utils.export_excel import export
    export(["ventas_ingresos_101", "riesgo_pais"], "reporte.xlsx")
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils.base_engine import get_read_engine

_ROOT         = Path(__file__).resolve().parents[1]
_EXPORT_DIR   = _ROOT / "exported_data"

# ---------------------------------------------------------------------------
# Agrupacion de tablas por modulo (prefijo conocido)
# ---------------------------------------------------------------------------

_GRUPOS = {
    "riesgo_pais":              ["riesgo_pais"],
    "pib_per_capita_nominal":   ["pib_per_capita_nominal"],
    "tipo_de_cambio":           ["tipo_de_cambio"],
    "reservas_internacionales": ["reservas_internacionales"],
    "depositos_gobierno_bce":   ["depositos_gobierno_bce"],
    "inflacion_ecuador":        ["inflacion_ecuador"],
    "empleo":                   ["empleo_"],
    "captaciones_publico":      ["captaciones_publico_", "cartera_publico_"],
    "captaciones_privado":      ["captaciones_privado_", "cartera_privado_"],
    "recaudacion_mensual":      ["recaudacion_mensual"],
    "mutualistas":              ["mutualistas_", "colocaciones_mutualistas_"],
    "pib_nominal_industria":    ["pib_nominal_industria_"],
    "ventas_sri":               ["ventas_"],
}


def _grupo_de(tabla: str) -> str:
    for grupo, prefijos in _GRUPOS.items():
        if any(tabla.lower().startswith(p.lower()) or tabla.lower() == p.lower().rstrip("_")
               for p in prefijos):
            return grupo
    return "otros"


# ---------------------------------------------------------------------------
# Consulta de tablas existentes
# ---------------------------------------------------------------------------

def list_tables(engine=None) -> list[str]:
    """Retorna lista de tablas existentes en la BD, ordenadas."""
    eng = engine or get_read_engine()
    from sqlalchemy import inspect as sa_inspect
    insp = sa_inspect(eng)
    return sorted(insp.get_table_names())


# ---------------------------------------------------------------------------
# Menu interactivo
# ---------------------------------------------------------------------------

def _print_menu(tablas: list[str]) -> None:
    grupos: dict[str, list[tuple[int, str]]] = {}
    for i, t in enumerate(tablas, 1):
        g = _grupo_de(t)
        grupos.setdefault(g, []).append((i, t))

    print("\n" + "=" * 60)
    print("  Tablas disponibles en data_verso")
    print("=" * 60)
    for grupo, items in grupos.items():
        print(f"\n  [{grupo}]")
        for idx, nombre in items:
            print(f"    {idx:>3}. {nombre}")
    print()


def _seleccionar(tablas: list[str]) -> list[str]:
    """
    Muestra menu e interpreta la seleccion del usuario.
    Retorna lista de nombres de tabla seleccionados.
    """
    _print_menu(tablas)

    print("Opciones de seleccion:")
    print("  [A]  Todas las tablas")
    print("  [G]  Por grupo/modulo (ej: empleo, ventas_sri)")
    print("  [N]  Por numero (ej: 1,3,5  o  2-8)")
    print()

    while True:
        opcion = input("Opcion [A/G/N]: ").strip().upper()

        if opcion == "A":
            return tablas

        elif opcion == "G":
            grupos_disponibles = sorted({_grupo_de(t) for t in tablas})
            print("\nGrupos disponibles:")
            for i, g in enumerate(grupos_disponibles, 1):
                print(f"  {i}. {g}")
            sel = input("\nNombres de grupo separados por coma: ").strip().lower()
            elegidos_g = {s.strip() for s in sel.split(",")}
            resultado = [t for t in tablas if _grupo_de(t) in elegidos_g]
            if not resultado:
                print("  [!] Ningun grupo coincide. Intenta de nuevo.")
                continue
            return resultado

        elif opcion == "N":
            entrada = input("Numeros (ej: 1,3,5  o  2-8): ").strip()
            indices: set[int] = set()
            for parte in entrada.split(","):
                parte = parte.strip()
                if "-" in parte:
                    try:
                        a, b = parte.split("-", 1)
                        indices.update(range(int(a), int(b) + 1))
                    except ValueError:
                        pass
                else:
                    try:
                        indices.add(int(parte))
                    except ValueError:
                        pass
            resultado = [tablas[i - 1] for i in sorted(indices) if 1 <= i <= len(tablas)]
            if not resultado:
                print("  [!] Seleccion invalida. Intenta de nuevo.")
                continue
            return resultado

        else:
            print("  [!] Opcion no reconocida. Escribe A, G o N.")


# ---------------------------------------------------------------------------
# Exportacion
# ---------------------------------------------------------------------------

def export(
    tablas: list[str],
    output: str | Path | None = None,
    limit: int | None = None,
    engine=None,
) -> Path:
    """
    Exporta las tablas indicadas a un archivo Excel (una hoja por tabla).

    Args:
        tablas:  Lista de nombres de tabla a exportar.
        output:  Ruta del archivo .xlsx de salida. Si es solo nombre de archivo
                 (sin directorio), se guarda en exported_data/. Si es None,
                 genera un nombre con timestamp en exported_data/.
        limit:   Maximo de filas por tabla (None = sin limite).
        engine:  Engine SQLAlchemy (None = usa get_read_engine()).

    Returns:
        Path del archivo generado.
    """
    if not tablas:
        print("[export] No hay tablas seleccionadas.")
        return _EXPORT_DIR / "export.xlsx"

    eng = engine or get_read_engine()

    # Resolver ruta de salida
    if output is None:
        ts  = datetime.now().strftime("%Y%m%d_%H%M")
        out = _EXPORT_DIR / f"export_{ts}.xlsx"
    else:
        p = Path(output)
        # Si no tiene directorio propio, meterlo en exported_data/
        out = p if p.parent != Path(".") else _EXPORT_DIR / p

    out.parent.mkdir(parents=True, exist_ok=True)

    limit_sql = f"TOP {limit} " if limit else ""

    print(f"\n[export] Exportando {len(tablas)} tabla(s) a '{out.name}' ...")

    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        for tabla in tablas:
            try:
                sql = f"SELECT {limit_sql}* FROM [{tabla}]"
                df = pd.read_sql(sql, eng)

                # Nombre de hoja: Excel permite max 31 chars
                sheet = tabla[:31]

                df.to_excel(writer, sheet_name=sheet, index=False)
                print(f"  OK  {tabla:<45} {len(df):>8} filas")

            except Exception as ex:
                print(f"  ERR {tabla}: {ex}")

    print(f"\n[export] Archivo guardado: {out.resolve()}")
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Exporta tablas de data_verso a Excel"
    )
    parser.add_argument(
        "--out", default=None, metavar="ARCHIVO.xlsx",
        help="Ruta del archivo de salida (por defecto: export_YYYYMMDD_HHMM.xlsx)"
    )
    parser.add_argument(
        "--limit", type=int, default=None, metavar="N",
        help="Maximo de filas por tabla (por defecto: sin limite)"
    )
    parser.add_argument(
        "--tablas", nargs="+", metavar="TABLA",
        help="Tablas a exportar directamente (omite el menu interactivo)"
    )
    args = parser.parse_args()

    engine = get_read_engine()
    todas  = list_tables(engine)

    if not todas:
        print("[export] No se encontraron tablas en la BD.")
        sys.exit(1)

    # Seleccion de tablas
    if args.tablas:
        tablas = [t for t in args.tablas if t in todas]
        no_enc = [t for t in args.tablas if t not in todas]
        if no_enc:
            print(f"[export] Tablas no encontradas: {no_enc}")
        if not tablas:
            sys.exit(1)
    else:
        tablas = _seleccionar(todas)

    export(tablas, args.out, limit=args.limit, engine=engine)


if __name__ == "__main__":
    main()
