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
│   ├── captaciones_financiero_publico/   ✓ implementado
│   ├── depositos_gobierno_bce/           ✓ implementado
│   ├── empleo/                           ✓ implementado
│   ├── inflacion_ecuador/                ✓ implementado
│   ├── reservas_internacionales/         ✓ implementado
│   ├── riesgo_pais/                      ✓ implementado
│   ├── tipo_de_cambio/                   ✓ implementado
│   │
│   ├── captaciones_financiero_privado/   ⚠ parcial (loader listo, bot pendiente)
│   │
│   ├── pib_nominal/                      ✗ pendiente
│   ├── pib_nominal_industria/            ✗ pendiente
│   ├── pib_per_capita_nominal/           ✗ pendiente
│   ├── pib_industria/                    ✗ pendiente
│   ├── recaudacion_mensual/              ✗ pendiente
│   ├── recaudacion_provincial/           ✗ pendiente
│   ├── tipo_de_cambio/                   ✗ pendiente
│   └── ventas_actividad_economica_sri/   ✗ pendiente
│
├── downloads/                  # Archivos descargados (ignorados por git)
├── requirements.txt
└── README.md
```

Cada fuente sigue el mismo patrón de tres archivos:

- **`bot.py`** — Solo descarga: navega el portal o consume la API, descarga archivos en `downloads/`.
- **`loader.py`** — Solo ETL: lee los archivos descargados, transforma y carga en SQL Server.
- **`main.py`** — Punto de entrada con CLI: orquesta bot + loader con argumentos de línea de comandos.

```bash
# Patrón común de ejecución
python main.py                  # flujo completo (descarga + carga)
python main.py --download-only  # solo descarga
python main.py --etl-only       # solo ETL (archivos ya en disco)
```

---

## Fuentes implementadas

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
| `captaciones_publico` | Depósitos de entidades financieras públicas por provincia y cantón |
| `cartera_publico` | Cartera de crédito de entidades financieras públicas |

---

### `depositos_gobierno_bce`

**URL:** https://contenido.bce.fin.ec/documentos/informacioneconomica/MonetarioFinanciero/ix_ReportesMonetarios.html
**Fuente:** Banco Central del Ecuador
**Periodicidad:** Semanal (última semana de cada año, desde 2012)
**Datos:** Información Monetaria Semanal (IMS) — todas las hojas del reporte BCE.

```bash
cd src/depositos_gobierno_bce
python main.py
python main.py --download-only
python main.py --etl-only
```

**Tablas:**

| Tabla | Hoja fuente | Formato | Descripción |
|---|---|---|---|
| `depositos_gobierno_ims1` | IMS1 | Ancho | Oferta monetaria — una fila por (año, mes) con 24 indicadores: RILD, emisión monetaria, cuasidinero, tasas, inflación |
| `depositos_gobierno_ims1_1` | IMS1.1 | Ancho | Oferta monetaria M1 y liquidez total M2 — una fila por (año, mes) con 15 indicadores |
| `depositos_gobierno_ims2` | IMS2 | Largo | Activos/pasivos por sector — una fila por (fecha_semana, indicador) |
| `depositos_gobierno_ims2_2` | IMS2 (2) | Largo | Segunda parte IMS2 |
| `depositos_gobierno_ims3` | IMS3 | Largo | Balance del Banco Central |
| `depositos_gobierno_ims4` | IMS4 | Largo | Balance sectorial BCE — incluye depósitos del Gobierno Central |
| `depositos_gobierno_ims5` | IMS5 | Largo | Otras sociedades de depósito |
| `depositos_gobierno_ims6` | IMS6 | Largo | Sector externo |
| `depositos_gobierno_ims7` | IMS7 | Largo | Tasas de interés |

**Notas:**
- Tablas IMS1 e IMS1.1 tienen formato ancho (columnas fijas por indicador); el resto son formato largo (`indicador`, `valor_millones`).
- Los labels se limpian automáticamente: se eliminan prefijos de numeración (`1.2 `, `A.`, etc.) y marcadores de nota al pie.
- La detección de columnas en IMS1 es por keyword, tolerando cambios de esquema entre años (ej. Dinero Electrónico añadido en ~2015).

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

### `reservas_internacionales`

**URL:** https://contenido.bce.fin.ec/documentos/informacioneconomica/MonetarioFinanciero/ix_ReservasInternacionales.html
**Fuente:** Banco Central del Ecuador
**Periodicidad:** Mensual (desde 2000) y Anual (desde 2000)
**Datos:** Reservas internacionales del Ecuador — posición neta en divisas, oro, DEG, posición FMI, ALADI, SUCRE y total RI.

```bash
cd src/reservas_internacionales
python main.py                  # descarga Excel + carga ambas tablas
python main.py --download-only
python main.py --etl-only       # usa Excel ya descargado
```

**Tablas:**

| Tabla | Descripción |
|---|---|
| `reservas_internacionales_anual` | Una fila por (anio, indicador) — 10 indicadores × 26 años (2000-2025) |
| `reservas_internacionales_mensual` | Una fila por (anio, mes_num, mes, indicador) — 10 indicadores × ~316 meses (ene 2000 – abr 2026) |

**Indicadores (ambas tablas):**
`Posición neta en divisas`, `Caja en divisas`, `Depósitos netos en bancos del exterior`, `Inversiones depósitos plazo y títulos`, `Oro`, `DEG`, `Posición de reserva en FMI`, `Posición con ALADI`, `Posición SUCRE`, `RI (total)`

**Notas:**
- La tabla mensual incluye `mes_num` (1-12) e índice clustered en `(anio, mes_num, indicador)` para ordenamiento calendario natural.
- Registros con valor `NULL` en el Excel se omiten (ej. SUCRE antes de su creación).

---

### `riesgo_pais`

**URL:** https://contenido.bce.fin.ec/documentos/informacioneconomica/SectorExterno/ix_SectorExternoPrin.html
**Fuente:** Banco Central del Ecuador (JSON estático, actualizado diariamente)
**Periodicidad:** Diario (desde 2017-01-01)
**Datos:** Índice EMBI — Riesgo País de Ecuador en puntos básicos.

```bash
cd src/riesgo_pais
python main.py             # fetch API + carga BD
python main.py --dry-run   # descarga y muestra sin cargar a BD
```

**No requiere Playwright** — el BCE expone los datos en un endpoint JSON directo:
`https://contenido.bce.fin.ec/documentos/informacioneconomica/indicadores/general/datos_formulario.json`

**Tabla `riesgo_pais`:**

| Columna | Tipo | Descripción |
|---|---|---|
| `fecha` | DATE | Fecha del dato (índice clustered) |
| `valor_riesgo_pais` | FLOAT | EMBI en puntos básicos |
| `fecha_actualizacion` | DATE | Fecha de última actualización en BCE |
| `hash_registro` | NVARCHAR(64) | SHA-256 para deduplicación |

---

## Pendiente de implementar

Los siguientes módulos tienen estructura de carpeta y archivos vacíos (stubs), pero aún no tienen bot ni loader funcionales:

| Módulo | Fuente | Periodicidad | Descripción |
|---|---|---|---|
| `captaciones_financiero_privado` | Superbancos | Mensual | Loader listo; falta bot de descarga |
| `pib_nominal` | BCE | Trimestral | PIB nominal total |
| `pib_nominal_industria` | BCE | Trimestral | PIB nominal por industria |
| `pib_per_capita_nominal` | BCE | Anual | PIB per cápita nominal |
| `pib_industria` | BCE | Trimestral | PIB por industria (variación) |
| `recaudacion_mensual` | SRI | Mensual | Recaudación tributaria mensual |
| `recaudacion_provincial` | SRI | Mensual | Recaudación tributaria por provincia |
| `ventas_actividad_economica_sri` | SRI | Mensual | Ventas por actividad económica |

---

## Dependencias

```
pandas          manipulación de DataFrames
openpyxl        lectura de archivos .xlsx
xlrd            lectura de archivos .xls (formato Excel 97-2003)
sqlalchemy      ORM y engine para SQL Server
pyodbc          driver ODBC para SQL Server
playwright      automatización del browser (portales con JS)
requests        descarga directa de archivos y APIs JSON
```

---

## Convenciones de implementación

- **Deduplicación:** cada fila tiene un hash SHA-256. La carga es idempotente — re-ejecutar no duplica datos.
- **PK no clusterizada + índice clustered:** `BIGINT IDENTITY` como PK física nonclustered; el índice clustered se define por las columnas de consulta más frecuentes (fecha, año, indicador, etc.).
- **Skip inteligente:** el bot verifica si el archivo ya está en disco (o si el tamaño remoto coincide) antes de descargar; el loader verifica hashes antes de insertar.
- **Tolerancia a cambios de formato:** los parsers localizan datos por etiqueta de texto o keyword en cabeceras, no por número de fila fijo, para tolerar reestructuraciones anuales de BCE/INEC.
- **Encoding:** los JSON y Excel del BCE se decodifican forzando UTF-8 para manejar correctamente caracteres como `ñ`, `á`, `é`, etc.
