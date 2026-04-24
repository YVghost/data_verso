"""
Bot de descarga: Captaciones (DEPÓSITOS) y Colocaciones (CARTERA) — Instituciones Públicas
Superbancos: https://www.superbancos.gob.ec/estadisticas/portalestudios/capcol-instituciones-publicas/

Misma estructura de portal OneDrive que el bot de bancos privados.
Ver captaciones_financiero_privado/bot.py para documentación completa de selectores y variantes.
"""

import sys
import re
import zipfile
import pandas as pd
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils.normalizer import clean_dataframe, normalize_numeric

BASE_URL = "https://www.superbancos.gob.ec/estadisticas/portalestudios/capcol-instituciones-publicas/"
DOWNLOAD_DIR = Path(__file__).resolve().parents[2] / "downloads" / "captaciones_financiero_publico"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

HIST_START_YEAR = 2016

AJAX_MIN_WAIT_MS  = 2_000
AJAX_CONTENT_MS   = 35_000
DOWNLOAD_TIMEOUT  = 120_000


# ---------------------------------------------------------------------------
# Fase 1 — descarga y extracción
# ---------------------------------------------------------------------------

def download_and_extract(start_year: int = None, end_year: int = None) -> dict:
    """
    Navega el portal año por año, descarga ZIPs y extrae Excels.

    Retorna:
        {
            "depositos": [Path, ...],
            "cartera":   [Path, ...]
        }
    """
    s = start_year or HIST_START_YEAR
    e = end_year or datetime.today().year
    result = {"depositos": [], "cartera": []}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        page.goto(BASE_URL, wait_until="domcontentloaded")
        _wait_root_level(page)

        for year in range(s, e + 1):
            print(f"\n[capcol_publico] ── Año {year} ──────────────────────────")
            try:
                paths = _process_year(page, year)
                result["depositos"].extend(paths["depositos"])
                result["cartera"].extend(paths["cartera"])
            except Exception as ex:
                print(f"[capcol_publico] ERROR año {year}: {ex}")
                _safe_goto_root(page)

        browser.close()

    return result


def _process_year(page, year: int) -> dict:
    result = {"depositos": [], "cartera": []}

    if not _click_folder_by_name(page, f"Año {year}"):
        print(f"  ✗ Carpeta 'Año {year}' no encontrada")
        return result
    _wait_folder_loaded(page)
    print(f"  ✓ Dentro de: Año {year}")

    direct_entries = _collect_file_entries(page)
    subfolders     = _collect_subfolder_names(page)

    if direct_entries:
        print(f"  Variante A — archivos directos: {len(direct_entries)}")
        _download_entries(page, year, direct_entries, result)

    elif subfolders:
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

    _navigate_back(page)
    _wait_root_level(page)
    print(f"  ✓ Vuelto al nivel raíz")

    return result


def _download_entries(page, year: int, entries: list, result: dict) -> None:
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
# Espera robusta para OneDrive
# ---------------------------------------------------------------------------

def _wait_root_level(page) -> None:
    page.wait_for_timeout(AJAX_MIN_WAIT_MS)
    try:
        page.wait_for_function(
            """() => {
                const folders = document.querySelectorAll('div.folders-container div.entry.folder');
                const yearFolders = Array.from(folders).filter(f => !f.classList.contains('pf'));
                return yearFolders.length >= 1;
            }""",
            timeout=AJAX_CONTENT_MS,
        )
    except PWTimeout:
        print("  [wait] Timeout esperando root — continuando...")
        page.wait_for_timeout(2_000)


def _wait_folder_loaded(page) -> None:
    page.wait_for_timeout(AJAX_MIN_WAIT_MS)
    try:
        page.wait_for_function(
            """() => {
                const backBtn = document.querySelector('div.entry.folder.pf');
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
    back_btn = page.locator("div.entry.folder.pf a.entry_link")
    if back_btn.count() > 0:
        back_btn.first.click()
    else:
        print("  [nav] 'Carpeta superior' no encontrada → recargando página")
        _safe_goto_root(page)


def _safe_goto_root(page) -> None:
    page.goto(BASE_URL, wait_until="domcontentloaded")
    _wait_root_level(page)


# ---------------------------------------------------------------------------
# Lectura y clasificación de archivos
# ---------------------------------------------------------------------------

def _collect_file_entries(page) -> list:
    entries = []
    file_divs = page.locator("div.files-container div.entry.file")
    count = file_divs.count()

    for i in range(count):
        div = file_divs.nth(i)
        entry_id  = div.get_attribute("data-id") or ""
        div_name  = (div.get_attribute("data-name") or "").strip()

        dl_btn    = div.locator("div.entry-download-button a.entry_action_download")
        dl_name   = (dl_btn.get_attribute("data-name") or f"{div_name}.zip").strip()
        dl_href   = dl_btn.get_attribute("href") or ""

        entries.append({
            "id":       entry_id,
            "name":     div_name,
            "filename": dl_name,
            "href":     dl_href,
        })

    return entries


def _collect_subfolder_names(page) -> list:
    names = []
    folders = page.locator("div.entry.folder:not(.pf)")
    for i in range(folders.count()):
        name = (folders.nth(i).get_attribute("data-name") or "").strip()
        if name:
            names.append(name)
    return names


def _classify_file(name: str) -> str | None:
    n = name.lower()
    if "captaciones" in n or "depositos" in n or "depósitos" in n:
        return "depositos"
    if "colocaciones" in n or "cartera" in n:
        return "cartera"
    return None


# ---------------------------------------------------------------------------
# Descarga de ZIP
# ---------------------------------------------------------------------------

def _download_entry(page, entry: dict, zip_path: Path) -> bool:
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
