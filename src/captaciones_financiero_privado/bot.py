"""
Bot de descarga: Captaciones (DEPÓSITOS) y Colocaciones (CARTERA) — Bancos Privados
Superbancos: https://www.superbancos.gob.ec/estadisticas/portalestudios/capcol-bancos/

Estructura del portal (dos variantes posibles según el año):
  Variante A — archivos directos en el año:
    Año XXXX/
      ├── Captaciones BANCOS PRIVADOS ... XXXX.zip
      ├── Colocaciones Cartera Comercial ... XXXX.zip
      └── ...

  Variante B — subcarpetas dentro del año:
    Año XXXX/
      ├── Captaciones Bancos Privados/
      │     └── Captaciones BANCOS PRIVADOS ... XXXX.zip
      └── Colocaciones/
            ├── Colocaciones Cartera Comercial ... XXXX.zip
            └── ...

El bot detecta automáticamente cuál variante aplica y navega en consecuencia.

Selectores confirmados:
  - Carpeta de año   : div.entry.folder[data-name="Año XXXX"] a.entry_link
  - Botón "atrás"    : div.entry.folder.pf a.entry_link  ("Carpeta superior")
  - Subcarpetas      : div.entry.folder:not(.pf)
  - Archivos ZIP     : div.files-container div.entry.file[data-id="..."]
  - Botón descarga   : div.entry-download-button a.entry_action_download  (href con dl=1)

Clasificación por nombre (data-name del archivo o subcarpeta):
  contiene "captaciones" o "depositos"   → tipo "depositos"
  contiene "colocaciones" o "cartera"    → tipo "cartera"
  (comparación case-insensitive)

Descarga local:
    downloads/captaciones_financiero_privado/<año>/depositos/<archivo>.zip
    downloads/captaciones_financiero_privado/<año>/cartera/<archivo>.zip

Fase 1: download_and_extract()  → descarga ZIPs y extrae Excels.
Fase 2: parse()                 → lee Excels y retorna DataFrames (pendiente).
"""

import sys
import re
import zipfile
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BASE_URL = "https://www.superbancos.gob.ec/estadisticas/portalestudios/capcol-bancos/"
DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "captaciones_financiero_privado"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

HIST_START_YEAR = 2014

# Pausa mínima para que OneDrive empiece a responder (puede tardar 1-10 s)
AJAX_MIN_WAIT_MS  = 2_000
# Tiempo máximo esperando que el contenido cargue
AJAX_CONTENT_MS   = 35_000
# Tiempo máximo para que se complete cada descarga de ZIP
DOWNLOAD_TIMEOUT  = 120_000


# ---------------------------------------------------------------------------
# Fase 1 — descarga y extracción
# ---------------------------------------------------------------------------

def download_and_extract(start_year: int = None, end_year: int = None) -> dict:
    """
    Navega el portal Superbancos año por año, descarga todos los ZIPs
    (1 de captaciones + hasta 5 de colocaciones) y extrae los Excels.

    Retorna:
        {
            "depositos": [Path, ...],   # Excels de Captaciones / DEPOSITOS
            "cartera":   [Path, ...]    # Excels de Colocaciones / CARTERA
        }
    """
    s = start_year or HIST_START_YEAR
    e = end_year or datetime.today().year
    result = {"depositos": [], "cartera": []}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # Carga inicial
        page.goto(BASE_URL, wait_until="domcontentloaded")
        _wait_root_level(page)

        for year in range(s, e + 1):
            print(f"\n[capcol_privado] ── Año {year} ──────────────────────────")
            try:
                paths = _process_year(page, year)
                result["depositos"].extend(paths["depositos"])
                result["cartera"].extend(paths["cartera"])
            except Exception as ex:
                print(f"[capcol_privado] ERROR año {year}: {ex}")
                # Volver al root para continuar con el siguiente año
                _safe_goto_root(page)

        browser.close()

    return result


def _process_year(page, year: int) -> dict:
    """
    Dentro del file browser:
      1. Entra a la carpeta del año.
      2. Detecta si hay archivos directos (Variante A) o subcarpetas (Variante B).
      3. Descarga y extrae según la variante detectada.
      4. Vuelve al root con "Carpeta superior".
    """
    result = {"depositos": [], "cartera": []}

    # ── 1. Entrar al año ─────────────────────────────────────────────────────
    if not _click_folder_by_name(page, f"Año {year}"):
        print(f"  ✗ Carpeta 'Año {year}' no encontrada")
        return result
    _wait_folder_loaded(page)
    print(f"  ✓ Dentro de: Año {year}")

    # ── 2. Detectar variante: archivos directos vs subcarpetas ────────────────
    direct_entries = _collect_file_entries(page)
    subfolders     = _collect_subfolder_names(page)

    if direct_entries:
        # Variante A: archivos directamente en la carpeta del año
        print(f"  Variante A — archivos directos: {len(direct_entries)}")
        _download_entries(page, year, direct_entries, result)

    elif subfolders:
        # Variante B: hay subcarpetas (Captaciones / Colocaciones)
        print(f"  Variante B — subcarpetas: {subfolders}")
        for sf_name in subfolders:
            print(f"    → Entrando: {sf_name}")
            if not _click_folder_by_name(page, sf_name):
                print(f"    ✗ No se pudo entrar a: {sf_name}")
                continue
            _wait_folder_loaded(page)
            entries = _collect_file_entries(page)
            print(f"    Archivos en '{sf_name}': {len(entries)}")
            _download_entries(page, year, entries, result)
            _navigate_back(page)
            _wait_folder_loaded(page)

    else:
        print(f"  [!] Sin archivos ni subcarpetas en Año {year}")

    # ── 3. Volver al root ─────────────────────────────────────────────────────
    _navigate_back(page)
    _wait_root_level(page)
    print(f"  ✓ Vuelto al nivel raíz")

    return result


def _download_entries(page, year: int, entries: list, result: dict) -> None:
    """Descarga y extrae todos los archivos de una lista de entries."""
    for entry in entries:
        tipo = _classify_file(entry["name"])
        if not tipo:
            print(f"  [?] Sin clasificar: {entry['name']}")
            continue

        tipo_dir = DOWNLOAD_DIR / str(year) / tipo
        tipo_dir.mkdir(parents=True, exist_ok=True)
        zip_path = tipo_dir / entry["filename"]

        if zip_path.exists():
            print(f"  [skip] Ya existe: {entry['filename']}")
        else:
            print(f"  [{tipo}] Descargando: {entry['filename']}")
            _download_entry(page, entry, zip_path)

        if zip_path.exists():
            result[tipo].extend(_extract_excels(zip_path, tipo_dir))


# ---------------------------------------------------------------------------
# Espera robusta para OneDrive (1-10 segundos de latencia)
# ---------------------------------------------------------------------------

def _wait_root_level(page) -> None:
    """
    Espera hasta que el root del file browser tenga carpetas de año visibles.
    En root no hay botón 'Carpeta superior' (div.entry.folder.pf).
    """
    page.wait_for_timeout(AJAX_MIN_WAIT_MS)
    try:
        page.wait_for_function(
            """() => {
                const folders = document.querySelectorAll('div.folders-container div.entry.folder');
                // En root esperamos varias carpetas de año; ninguna debe ser .pf
                const yearFolders = Array.from(folders).filter(f => !f.classList.contains('pf'));
                return yearFolders.length >= 1;
            }""",
            timeout=AJAX_CONTENT_MS,
        )
    except PWTimeout:
        print("  [wait] Timeout esperando root — continuando...")
        page.wait_for_timeout(2_000)


def _wait_folder_loaded(page) -> None:
    """
    Espera a que cualquier carpeta AJAX haya cargado su contenido.
    Solo requiere que aparezca el botón 'Carpeta superior' (.pf), que siempre
    está presente al entrar en cualquier subcarpeta (año o subcarpeta de año).
    No exige archivos directos — puede haber solo subcarpetas.
    """
    page.wait_for_timeout(AJAX_MIN_WAIT_MS)
    try:
        page.wait_for_function(
            """() => {
                const backBtn = document.querySelector('div.entry.folder.pf');
                // Además esperamos que el contenedor principal tenga algún hijo
                // (archivo o subcarpeta), para asegurarnos de que el AJAX terminó.
                const hasContent =
                    document.querySelectorAll('div.files-container div.entry').length > 0 ||
                    document.querySelectorAll('div.folders-container div.entry.folder').length > 1;
                return backBtn !== null && hasContent;
            }""",
            timeout=AJAX_CONTENT_MS,
        )
    except PWTimeout:
        print("  [wait] Timeout esperando contenido de carpeta — continuando...")
        page.wait_for_timeout(2_000)


# ---------------------------------------------------------------------------
# Helpers de navegación
# ---------------------------------------------------------------------------

def _click_folder_by_name(page, folder_name: str) -> bool:
    """
    Busca una carpeta cuyo data-name contenga folder_name (case-insensitive)
    y hace clic en su a.entry_link. Excluye el botón 'Carpeta superior' (.pf).
    """
    entries = page.locator("div.entry.folder:not(.pf)")
    count = entries.count()
    for i in range(count):
        entry = entries.nth(i)
        data_name = (entry.get_attribute("data-name") or "").strip()
        if folder_name.lower() in data_name.lower():
            entry.locator("a.entry_link").click()
            return True
    return False


def _navigate_back(page) -> None:
    """
    Navega al nivel superior haciendo clic en 'Carpeta superior' (div.entry.folder.pf).
    Si no existe, recarga la página como fallback.
    """
    back_btn = page.locator("div.entry.folder.pf a.entry_link")
    if back_btn.count() > 0:
        back_btn.first.click()
    else:
        print("  [nav] 'Carpeta superior' no encontrada → recargando página")
        _safe_goto_root(page)


def _safe_goto_root(page) -> None:
    """Recarga la página y espera el root (fallback de navegación)."""
    page.goto(BASE_URL, wait_until="domcontentloaded")
    _wait_root_level(page)


# ---------------------------------------------------------------------------
# Lectura y clasificación de archivos
# ---------------------------------------------------------------------------

def _collect_file_entries(page) -> list:
    """
    Lee TODOS los archivos visibles en div.files-container y retorna su metadata.
    Se recoge toda la info antes de descargar para evitar referencias obsoletas.
    """
    entries = []
    file_divs = page.locator("div.files-container div.entry.file")
    count = file_divs.count()

    for i in range(count):
        div = file_divs.nth(i)
        entry_id  = div.get_attribute("data-id") or ""
        div_name  = (div.get_attribute("data-name") or "").strip()

        # El botón de descarga (dl=1) tiene el nombre con extensión .zip
        dl_btn     = div.locator("div.entry-download-button a.entry_action_download")
        dl_name    = (dl_btn.get_attribute("data-name") or f"{div_name}.zip").strip()
        dl_href    = dl_btn.get_attribute("href") or ""

        entries.append({
            "id":       entry_id,
            "name":     div_name,    # sin extensión (para clasificar)
            "filename": dl_name,     # con .zip (para guardar)
            "href":     dl_href,
        })

    return entries


def _collect_subfolder_names(page) -> list:
    """
    Retorna los data-name de todas las subcarpetas visibles (excluye 'Carpeta superior' .pf).
    Se usa cuando el año contiene subcarpetas en lugar de archivos directos.
    """
    names = []
    folders = page.locator("div.entry.folder:not(.pf)")
    for i in range(folders.count()):
        name = (folders.nth(i).get_attribute("data-name") or "").strip()
        if name:
            names.append(name)
    return names


def _classify_file(name: str) -> str | None:
    """
    Clasifica un archivo por su nombre (data-name del div.entry.file).
    Retorna "depositos", "cartera", o None si no se puede clasificar.
    """
    n = name.lower()
    if "captaciones" in n or "depositos" in n:
        return "depositos"
    if "colocaciones" in n or "cartera" in n:
        return "cartera"
    return None


# ---------------------------------------------------------------------------
# Descarga de ZIP
# ---------------------------------------------------------------------------

def _download_entry(page, entry: dict, zip_path: Path) -> bool:
    """
    Descarga el ZIP usando el href real del botón (dl=1) a través de page.request,
    que reutiliza la sesión y cookies del navegador sin necesidad de capturar eventos.
    """
    href = entry.get("href", "")
    if not href or not href.startswith("http"):
        print(f"  ✗ Sin href válido: {entry['filename']}")
        return False
    try:
        response = page.request.get(href, timeout=DOWNLOAD_TIMEOUT)
        if not response.ok:
            print(f"  ✗ HTTP {response.status}: {entry['filename']}")
            return False
        zip_path.write_bytes(response.body())
        print(f"  ✓ Guardado: {zip_path.name} ({zip_path.stat().st_size:,} bytes)")
        return True
    except Exception as ex:
        print(f"  ✗ Error ({entry['filename']}): {ex}")
        return False


# ---------------------------------------------------------------------------
# Extracción de Excels desde ZIP
# ---------------------------------------------------------------------------

def _extract_excels(zip_path: Path, dest_dir: Path) -> list:
    """
    Extrae solo los archivos .xlsx / .xls del ZIP en dest_dir.
    Salta archivos que ya existen. Retorna lista de Paths extraídos.
    """
    extracted = []
    if not zip_path.exists():
        return extracted

    with zipfile.ZipFile(zip_path, "r") as z:
        for name in z.namelist():
            if not re.search(r"\.xlsx?$", name, re.IGNORECASE):
                continue
            flat_name = Path(name).name
            dest_path = dest_dir / flat_name
            if not dest_path.exists():
                dest_path.write_bytes(z.read(name))
                print(f"  Extraído: {flat_name}")
            extracted.append(dest_path)

    return extracted


