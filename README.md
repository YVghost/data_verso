# data_verso

Pipeline de ETL para indicadores económicos y financieros de Ecuador. Descarga datos desde portales públicos (Superbancos, BCE, SRI, INEC) y los carga en una base de datos SQL Server local.

---

## Requisitos previos

| Herramienta | Versión mínima |
|---|---|
| Python | 3.11+ |
| SQL Server | 2019+ (local, autenticación Windows) |
| ODBC Driver | 17 for SQL Server |
| Playwright | instalado con `playwright install chromium` |

---

## Instalación

```bash
# 1. Clonar el repositorio
git clone <url-del-repo>
cd data_verso

# 2. Crear y activar entorno virtual
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Instalar el browser de Playwright
playwright install chromium
```

### Base de datos

Crear la base de datos en SQL Server antes de ejecutar cualquier fuente:

```sql
CREATE DATABASE data_verso;
```

La conexión usa autenticación Windows (Trusted_Connection). Si necesitas usuario y contraseña, edita `utils/base_engine.py`.

---

## Estructura del proyecto

```
data_verso/
├── utils/
│   ├── base_engine.py          # Conexión SQLAlchemy a SQL Server
│   └── normalizer.py           # Funciones de limpieza de texto y números
│
├── src/
│   ├── captaciones_financiero_privado/   ← implementado ✓
│   │   ├── bot.py              # Playwright: descarga ZIPs de Superbancos
│   │   ├── loader_depositos.py # ETL depósitos → stg_captaciones → captaciones
│   │   ├── loader_cartera.py   # ETL cartera   → stg_cartera     → cartera
│   │   └── main.py             # Punto de entrada con CLI
│   │
│   ├── captaciones_financiero_publico/   ← en desarrollo
│   ├── depositos_gobierno_bce/
│   ├── empleo/
│   ├── inflacion_ecuador/
│   ├── pib_industria/
│   ├── pib_nominal/
│   ├── pib_nominal_industria/
│   ├── pib_per_capita_nominal/
│   ├── recaudacion_mensual/
│   ├── recaudacion_provincial/
│   ├── reservas_internacionales/
│   ├── riesgo_pais/
│   ├── tipo_de_cambio/
│   └── ventas_actividad_economica_sri/
│
├── downloads/                  # Archivos descargados (ignorados por git)
├── requirements.txt
└── README.md
```

---

## Fuente: `captaciones_financiero_privado`

**URL:** https://www.superbancos.gob.ec/estadisticas/portalestudios/capcol-bancos/  
**Periodicidad:** Mensual, desde 2014  
**Datos:** Captaciones (depósitos) y Colocaciones (cartera de crédito) de bancos privados del Ecuador, desagregados por provincia y cantón.

### Cómo ejecutar

```bash
cd src/captaciones_financiero_privado

# Flujo completo: descarga todo desde 2014 hasta hoy y carga a la BD
python main.py

# Flujo completo para un rango de años específico
python main.py --start 2021 --end 2024

# Solo descargar archivos (sin tocar la BD)
python main.py --download-only

# Solo ejecutar el ETL sobre archivos ya descargados
python main.py --etl-only

# Procesar únicamente depósitos o únicamente cartera
python main.py --mode depositos
python main.py --mode cartera --start 2022
```

### Flujo interno

```
Portal Superbancos (OneDrive file browser)
        │
        ▼  bot.py (Playwright)
   downloads/captaciones_financiero_privado/
        <año>/depositos/*.xlsx
        <año>/cartera/*.xlsx
        │
        ├─▶ loader_depositos.py
        │       stg_captaciones   (staging, todos los intentos)
        │            └─▶ captaciones   (tabla final consolidada)
        │
        └─▶ loader_cartera.py
                stg_cartera       (staging, todos los intentos)
                     └─▶ cartera         (tabla final consolidada)
```

### Tablas en SQL Server

#### `captaciones` — Depósitos bancarios

| Columna | Tipo | Descripción |
|---|---|---|
| id | INT | PK (no clustered) |
| fecha | DATE | Fin de mes del período |
| entidad | NVARCHAR | Nombre del banco |
| region | NVARCHAR | Región geográfica |
| provincia | NVARCHAR | Provincia |
| canton | NVARCHAR | Cantón |
| cuenta | NVARCHAR | Código de cuenta contable |
| tipo_deposito | NVARCHAR | Tipo de depósito (a la vista, plazo, etc.) |
| numero_clientes | FLOAT | Número de clientes |
| numero_cuentas | FLOAT | Número de cuentas |
| saldo | FLOAT | Saldo en USD |
| hash_registro | NVARCHAR(64) | SHA-256 para deduplicación |
| fecha_carga | DATETIME | Timestamp de carga |

Índice clustered en `(fecha, provincia, canton)` para consultas geográfico-temporales.

#### `cartera` — Cartera de crédito

| Columna | Tipo | Descripción |
|---|---|---|
| id | INT | PK (no clustered) |
| fecha | DATE | Fin de mes del período |
| entidad | NVARCHAR | Nombre del banco |
| provincia | NVARCHAR | Provincia |
| canton | NVARCHAR | Cantón |
| tipo_colocacion | NVARCHAR | Segmento de crédito (consumo, comercial, etc.) |
| subtipo_colocacion | NVARCHAR | Subsegmento (prioritario, ordinario, etc.) |
| por_vencer | FLOAT | Cartera por vencer (USD) |
| no_devenga_intereses | FLOAT | Cartera que no devenga intereses (USD) |
| vencida | FLOAT | Cartera vencida (USD) |
| total_cartera | FLOAT | Saldo total (USD) |
| morosidad | FLOAT | Índice de morosidad (ratio) |
| hash_registro | NVARCHAR(64) | SHA-256 para deduplicación |
| fecha_carga | DATETIME | Timestamp de carga |

Índice clustered en `(fecha, provincia, canton)`.

### Notas de implementación

- **Variante A / B:** El portal tiene dos estructuras de carpetas según el año. El bot detecta automáticamente si los ZIPs están directamente en la carpeta del año (variante A) o dentro de subcarpetas (variante B).
- **Hojas tabular vs reporte:** Cada Excel puede tener una hoja de base tabular (datos largos) y una hoja de reporte (datos anchos con fechas como columnas). El loader usa la tabular cuando existe; si no, usa el reporte.
- **Grupos de métricas:** Las hojas de reporte 2021+ tienen una fila de grupos que indica a qué métrica pertenece cada bloque de columnas de fecha (CARTERA POR VENCER, NO DEVENGA INTERESES, CARTERA VENCIDA, SALDO TOTAL, MOROSIDAD).
- **Deduplicación:** Cada fila tiene un hash SHA-256 de sus columnas clave. La carga a staging y al final es idempotente: re-ejecutar no duplica datos.
- **Migración no destructiva:** Si se añaden columnas nuevas a futuro, `_ensure_columns()` las agrega con ALTER TABLE sin recrear las tablas.

---

## Dependencias principales

```
pandas          manipulación de DataFrames
openpyxl        lectura de archivos Excel (.xlsx)
sqlalchemy      ORM y engine para SQL Server
pyodbc          driver ODBC para SQL Server
playwright      automatización del browser para descarga
```

---

## Convenciones de código

Cada fuente sigue el mismo patrón de tres archivos:

- **`bot.py`** — Solo descarga: navega el portal, descarga ZIPs, extrae Excels en `downloads/`.
- **`loader_*.py`** — Solo ETL: lee los Excels extraídos, transforma y carga en SQL Server.
- **`main.py`** — Punto de entrada con CLI: orquesta bot + loaders con argumentos de línea de comandos.
