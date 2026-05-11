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
│   ├── captaciones_financiero_publico/   ← implementado ✓
│   ├── depositos_gobierno_bce/           ← implementado ✓
│   ├── empleo/                           ← implementado ✓
│   ├── inflacion_ecuador/                ← implementado ✓
│   ├── reservas_internacionales/         ← implementado ✓
│   ├── riesgo_pais/                      ← implementado ✓
│   ├── tipo_de_cambio/                   ← implementado ✓
│   ├── ventas_actividad_economica_sri/   ← implementado ✓
│   ├── recaudacion_mensual/              ← implementado ✓
│   ├── recaudacion_provincial/           ← implementado ✓
│   ├── pib_nominal/                      ← implementado ✓
│   ├── pib_nominal_industria/            ← implementado ✓
│   ├── pib_per_capita_nominal/           ← implementado ✓
│   └── pib_industria/                    ← implementado ✓
│
├── downloads/                  # Archivos descargados (ignorados por git)
├── requirements.txt
└── README.md
```

Cada fuente sigue el mismo patrón de tres archivos:

- **`bot.py`** — Solo descarga: navega el portal, descarga archivos en `downloads/`.
- **`loader.py`** — Solo ETL: lee los archivos descargados, transforma y carga en SQL Server.
- **`main.py`** — Punto de entrada con CLI: orquesta bot + loader con argumentos de línea de comandos.

```bash
# Patrón común de ejecución
python main.py                  # flujo completo
python main.py --download-only  # solo descarga
python main.py --etl-only       # solo ETL (archivos ya en disco)
```

---

## Fuentes implementadas

### `captaciones_financiero_privado`

**URL:** https://www.superbancos.gob.ec/estadisticas/portalestudios/capcol-bancos/  
**Fuente:** Superintendencia de Bancos  
**Periodicidad:** Mensual, desde 2014  
**Datos:** Captaciones (depósitos) y cartera de crédito de bancos privados, por provincia y cantón.

```bash
cd src/captaciones_financiero_privado
python main.py                         # flujo completo
python main.py --start 2021 --end 2024 # rango de años
python main.py --mode depositos        # solo depósitos
python main.py --mode cartera          # solo cartera
```

**Tablas:**

| Tabla | Descripción |
|---|---|
| `captaciones` | Depósitos bancarios por entidad, provincia y cantón |
| `cartera` | Cartera de crédito por segmento, provincia y cantón |

---

### `captaciones_financiero_publico`

**URL:** https://www.superbancos.gob.ec/estadisticas/portalestudios/capcol-instituciones-publicas/  
**Fuente:** Superintendencia de Bancos  
**Periodicidad:** Mensual  
**Datos:** Captaciones y cartera de instituciones financieras públicas (BanEcuador, CFN, BEV, etc.).

```bash
cd src/captaciones_financiero_publico
python main.py
python main.py --mode depositos --start 2022
```

**Tablas:**

| Tabla | Descripción |
|---|---|
| `captaciones_publico` | Depósitos de entidades financieras públicas |
| `cartera_publico` | Cartera de crédito de entidades financieras públicas |

---

### `depositos_gobierno_bce`

**URL:** https://contenido.bce.fin.ec/documentos/informacioneconomica/MonetarioFinanciero/ix_ReportesMonetarios.html  
**Fuente:** Banco Central del Ecuador  
**Periodicidad:** Semanal (última semana de cada año, desde 2012)  
**Datos:** Balance Sectorial del BCE — depósitos del Gobierno Central, extraídos de la hoja IMS4/IMS5.

```bash
cd src/depositos_gobierno_bce
python main.py
python main.py --download-only
python main.py --etl-only
```

**Tabla:** `depositos_gobierno_bce`

| Columna | Tipo | Descripción |
|---|---|---|
| fecha_semana | DATE | Fecha de la semana (última del año) |
| anio | INT | Año |
| dep_transferibles_tot | FLOAT | Depósitos transferibles sector público incluídos en dinero amplio (MM USD) |
| gc_dep_transferibles | FLOAT | Depósitos transferibles Gobierno Central excluídos (MM USD) |
| otros_dep_tot | FLOAT | Total otros depósitos excluídos (MM USD) |
| gc_otros_dep | FLOAT | Otros depósitos del Gobierno Central (MM USD) |
| hash_registro | NVARCHAR(64) | SHA-256 para deduplicación |

**Notas:**
- Los archivos `.xls` de 2012-2013 usan la hoja `IMS5`; desde 2014 usan `IMS4` (mismo esquema de datos).
- La detección de hoja es automática por contenido ("BALANCE SECTORIAL: BANCO CENTRAL").
- Las filas se localizan por etiqueta de texto, no por número fijo, para tolerar cambios de formato año a año.

---

### `empleo`

**URL (trimestral):** https://www.ecuadorencifras.gob.ec/enemdu-trimestral/  
**URL (mensual):** https://www.ecuadorencifras.gob.ec/estadisticas-laborales-enemdu/  
**Fuente:** INEC — ENEMDU  
**Periodicidad:** Trimestral (desde 2020) y Mensual (histórico desde 2007)  
**Datos:** Mercado laboral — poblaciones, tasas, caracterización del empleo y sectorización.

```bash
cd src/empleo
python main.py                             # trimestral + mensual
python main.py --tipo trimestral
python main.py --tipo mensual --start 2022
```

**Tablas:**

| Tabla | Descripción |
|---|---|
| `empleo_poblacion` | PEA, PEI, PET, ocupados, desocupados — desagregados por área, edad, sexo, etnia |
| `empleo_tasas` | Tasas de empleo, desempleo, subempleo, brecha |
| `empleo_caracterizacion` | Distribución de empleados, plenos, subempleados, desocupados por categoría |
| `empleo_sectorizacion` | Empleo por sector económico (formal, informal, doméstico, etc.) |

Columna `tipo_periodo`: `'trimestral'` | `'mensual'`

---

### `inflacion_ecuador`

**URL:** https://www.ecuadorencifras.gob.ec/inflacion/  
**Fuente:** INEC — Índice de Precios al Consumidor (IPC)  
**Periodicidad:** Mensual (serie histórica desde 1969)  
**Datos:** Variaciones mensuales/anuales del IPC, indicadores descriptivos, incidencias y variaciones por región y ciudad.

```bash
cd src/inflacion_ecuador
python main.py
python main.py --download-only
python main.py --etl-only
```

El bot descarga el ZIP del mes más reciente disponible (sondeo HEAD desde el mes actual hacia atrás). Extrae todos los XLS/XLSX que contiene.

**Tablas:**

| Tabla | Archivo fuente | Descripción |
|---|---|---|
| `inflacion_ecuador_variacion_mensual` | `SERIE HISTORICA IPC_*.xls` | Variación mensual del IPC por división CCIF |
| `inflacion_ecuador_variacion_anual` | `SERIE HISTORICA IPC_*.xls` | Variación anual del IPC por división CCIF |
| `inflacion_ecuador_indicadores_variacion_mensual` | `ipc_indicadores_descriptivos_*.xlsx` | Indicadores mensuales (general, alimentos, bienes, servicios, etc.) — formato ancho |
| `inflacion_ecuador_indicadores_variacion_anual` | `ipc_indicadores_descriptivos_*.xlsx` | Indicadores anuales — formato ancho |
| `inflacion_ecuador_series_incidencias_mensual` | `ipc_incid_nac_div_*.xlsx` | Incidencias mensuales por división CCIF |
| `inflacion_ecuador_series_incidencias_anual` | `ipc_incid_nac_div_*.xlsx` | Incidencias anuales por división CCIF |
| `inflacion_ecuador_series_ipc_mensual` | `ipc_var_men_nac_reg_ciud[_emp]_*.xlsx` | Variación mensual por región/ciudad y CCIF (normal + empalmada) |
| `inflacion_ecuador_series_ipc_anual` | `ipc_var_anu_nac_reg_ciud[_emp]_*.xlsx` | Variación anual por región/ciudad y CCIF (normal + empalmada) |

Columna `es_empalmada`: `'Si'` | `'No'`  
Se excluyen hojas: Esmeraldas, Machala, Sto. Domingo.

---

### Otras fuentes

| Módulo | Fuente | Periodicidad | Tabla(s) |
|---|---|---|---|
| `reservas_internacionales` | BCE | Mensual | `reservas_internacionales` |
| `riesgo_pais` | BCE | Diario | `riesgo_pais` |
| `tipo_de_cambio` | BCE | Diario | `tipo_de_cambio` |
| `ventas_actividad_economica_sri` | SRI | Mensual | `ventas_actividad_economica_sri` |
| `recaudacion_mensual` | SRI | Mensual | `recaudacion_mensual` |
| `recaudacion_provincial` | SRI | Mensual | `recaudacion_provincial` |
| `pib_nominal` | BCE | Trimestral | `pib_nominal` |
| `pib_nominal_industria` | BCE | Trimestral | `pib_nominal_industria` |
| `pib_per_capita_nominal` | BCE | Anual | `pib_per_capita_nominal` |
| `pib_industria` | BCE | Trimestral | `pib_industria` |

---

## Dependencias

```
pandas          manipulación de DataFrames
openpyxl        lectura de archivos .xlsx
xlrd            lectura de archivos .xls (formato Excel 97-2003)
sqlalchemy      ORM y engine para SQL Server
pyodbc          driver ODBC para SQL Server
playwright      automatización del browser (portales con JS)
requests        descarga directa de archivos (HEAD probing + GET)
```

---

## Convenciones de implementación

- **Deduplicación:** cada fila tiene un hash SHA-256. La carga es idempotente — re-ejecutar no duplica datos.
- **PK no clusterizada + índice clustered:** `BIGINT IDENTITY` como PK física nonclustered; el índice clustered se crea por las columnas de consulta más frecuentes (fecha, región, etc.).
- **Skip inteligente:** el bot verifica si el archivo ya está en disco antes de descargar; el loader verifica hashes antes de insertar.
- **Tolerancia a cambios de formato:** los parsers buscan datos por etiqueta de texto o patrón de cabecera, no por número de fila fijo, para tolerar reestructuraciones anuales del BCE/INEC.
