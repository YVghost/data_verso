"""
Orquestador global — data_verso

Ejecuta todos los ETL implementados en orden. Cada modulo corre de forma
independiente: si uno falla, los demas continuan.

Orden de ejecucion:
  1.  riesgo_pais                    JSON directo BCE   (sin Playwright)
  2.  pib_per_capita_nominal         BCE Excel
  3.  tipo_de_cambio                 BCE Excel
  4.  reservas_internacionales       BCE Excel + Playwright
  5.  depositos_gobierno_bce         BCE XLS/XLSX semanales (2012-presente)
  6.  inflacion_ecuador              INEC ZIP mensual
  7.  empleo                         INEC CSVs trimestrales + mensuales (Playwright)
  8.  captaciones_financiero_publico Superbancos ZIPs anuales (Playwright)
  9.  captaciones_financiero_privado Superbancos ZIPs anuales (Playwright)
  10. recaudacion_mensual            SRI CSVs anuales (2017-presente)
  11. mutualistas                    SEPS ZIPs anuales — captaciones (3 tablas)
                                      + colocaciones (8 tablas), 2017-presente
  12. pib_nominal_industria          BCE Excel trimestrales — VAB por industrias
                                      (2 tablas: bruto + ajustado, 2023-presente)
  13. ventas_actividad_economica_sri SRI Saiku REST API — 6 tablas por
                                      declaracion/metrica (101/103/104 CIIU,
                                      2020-presente, descarga automatica)
  14. pib_nominal_oferta             BCE Excel trimestrales — Oferta y Utilizacion
                                      de Bienes y Servicios (2 tablas: bruto +
                                      ajustado, ediciones 2023-presente,
                                      datos desde 2000.I)

Uso:
  python main.py                              # todos los modulos
  python main.py -m riesgo_pais reservas      # modulos especificos (substring)
  python main.py --etl-only                   # solo ETL, sin descargar
  python main.py --download-only              # solo descarga, sin BD
  python main.py --list                       # muestra modulos disponibles
"""

import argparse
import importlib.util
import sys
import time
from datetime import datetime
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"

# Orden de ejecucion y argumentos por modulo
# (nombre, kwargs para run())
_MODULES = [
    ("riesgo_pais",                    {}),
    ("pib_per_capita_nominal",         {}),
    ("tipo_de_cambio",                 {}),
    ("reservas_internacionales",       {}),
    ("depositos_gobierno_bce",         {}),
    ("inflacion_ecuador",              {}),
    ("empleo",                         {}),
    ("captaciones_financiero_publico", {}),
    ("captaciones_financiero_privado", {}),
    ("recaudacion_mensual",           {}),
    ("mutualistas",                   {}),
    ("pib_nominal_industria",         {}),
    ("ventas_actividad_economica_sri", {}),
    ("pib_nominal_oferta",            {}),
]


# ---------------------------------------------------------------------------
# Cargador de modulos
# ---------------------------------------------------------------------------

_GENERIC_NAMES = {
    "bot", "loader", "loader_depositos", "loader_cartera",
    "loader_cartera_privada", "loader_depositos_privado",
    "loader_recaudacion", "loader_captaciones",
    "bot_colocaciones", "loader_colocaciones",
}


def _load_main(module_name: str):
    """
    Carga el main.py de un modulo limpiando primero los nombres genericos
    (bot, loader, etc.) del cache de sys.modules para evitar colisiones
    entre modulos que usan los mismos nombres de archivo.
    """
    mod_dir   = SRC / module_name
    main_path = mod_dir / "main.py"
    if not main_path.exists():
        raise FileNotFoundError(f"No existe: {main_path}")

    # Limpiar modulos genericos del cache antes de importar
    for name in list(sys.modules.keys()):
        if name in _GENERIC_NAMES or name.startswith(f"_etl_"):
            del sys.modules[name]

    # Asegurar que el directorio del modulo este al frente del path
    mod_dir_str = str(mod_dir)
    # Quitar versiones anteriores del mismo directorio si las hay
    sys.path = [p for p in sys.path if p not in {str(SRC / m) for m, _ in _MODULES}]
    sys.path.insert(0, mod_dir_str)

    spec = importlib.util.spec_from_file_location(
        f"_etl_{module_name}", main_path
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Ejecucion por modulo
# ---------------------------------------------------------------------------

def _run_module(name: str, kwargs: dict) -> bool:
    """
    Carga y ejecuta run(**kwargs) del modulo indicado.
    Retorna True si exitoso, False si hubo error.
    """
    try:
        mod = _load_main(name)
        if not hasattr(mod, "run"):
            print(f"  [!] {name}: sin funcion run() — omitido")
            return False
        mod.run(**kwargs)
        return True
    except Exception as ex:
        print(f"  [ERROR] {name}: {ex}")
        return False


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def run(
    modulos: list[str] | None = None,
    download_only: bool = False,
    etl_only: bool = False,
) -> None:
    """
    Ejecuta los modulos en orden.
    modulos: lista de substrings para filtrar por nombre (None = todos).
    """
    # Filtrar modulos si se especificaron
    targets = _MODULES
    if modulos:
        targets = [
            (name, kw) for name, kw in _MODULES
            if any(m.lower() in name.lower() for m in modulos)
        ]
        if not targets:
            print(f"[main] Ningun modulo coincide con: {modulos}")
            return

    # Armar kwargs comunes segun flags
    extra: dict = {}
    if download_only:
        extra["download_only"] = True
    if etl_only:
        extra["etl_only"] = True

    print(f"\n{'='*60}")
    print(f"  data_verso - ETL global")
    print(f"  Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Modulos: {len(targets)}")
    if download_only:
        print("  Modo: solo descarga")
    elif etl_only:
        print("  Modo: solo ETL")
    print(f"{'='*60}\n")

    resultados = {}
    for name, base_kw in targets:
        kw = {**base_kw, **extra}
        # riesgo_pais usa dry_run en vez de download_only/etl_only
        if name == "riesgo_pais":
            kw = {}

        print(f"\n{'-'*60}")
        print(f"  MODULO: {name}")
        print(f"{'-'*60}")
        t0 = time.time()
        ok = _run_module(name, kw)
        elapsed = time.time() - t0
        resultados[name] = ("OK" if ok else "ERROR", elapsed)

    # Resumen final
    print(f"\n{'='*60}")
    print(f"  RESUMEN")
    print(f"{'='*60}")
    total_ok  = 0
    total_err = 0
    for name, (status, elapsed) in resultados.items():
        icon = "OK" if status == "OK" else "ERR"
        print(f"  {icon} {name:<40} {elapsed:>6.1f}s  [{status}]")
        if status == "OK":
            total_ok += 1
        else:
            total_err += 1
    print(f"{'-'*60}")
    print(f"  Completados: {total_ok}/{len(resultados)}  "
          f"Errores: {total_err}")
    print(f"  Fin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Orquestador global ETL — data_verso"
    )
    parser.add_argument(
        "-m", "--modulos", nargs="+", metavar="NOMBRE",
        help="Uno o mas nombres de modulo (substring). Por defecto: todos."
    )
    parser.add_argument(
        "--download-only", action="store_true",
        help="Solo descarga archivos, sin cargar a la BD"
    )
    parser.add_argument(
        "--etl-only", action="store_true",
        help="Solo ejecuta ETL sobre archivos ya descargados"
    )
    parser.add_argument(
        "--list", action="store_true",
        help="Muestra los modulos disponibles y sale"
    )

    args = parser.parse_args()

    if args.download_only and args.etl_only:
        parser.error("--download-only y --etl-only son mutuamente excluyentes.")

    if args.list:
        print("\nModulos disponibles (en orden de ejecucion):")
        for i, (name, _) in enumerate(_MODULES, 1):
            print(f"  {i}. {name}")
        print()
        sys.exit(0)

    run(
        modulos=args.modulos,
        download_only=args.download_only,
        etl_only=args.etl_only,
    )
