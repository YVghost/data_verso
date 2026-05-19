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
│   ├── captaciones_financiero_privado/   ✓ implementado
│   ├── depositos_gobierno_bce/           ✓ implementado
│   ├── empleo/                           ✓ implementado
│   ├── inflacion_ecuador/                ✓ implementado
│   ├── reservas_internacionales/         ✓ implementado
│   ├── pib_per_capita_nominal/           ✓ implementado
│   ├── riesgo_pais/                      ✓ implementado
│   ├── tipo_de_cambio/                   ✓ implementado
│   ├── recaudacion_mensual/              ✓ implementado
│   ├── mutualistas/                      ✓ implementado
│   │
│   ├── pib_nominal/                      ✗ pendiente (stub)
│   ├── pib_nominal_industria/            ✗ pendiente (stub)
│   ├── pib_industria/                    ✗ pendiente (stub)
│   └── ventas_actividad_economica_sri/   ✗ pendiente (stub)
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

### `captaciones_financiero_privado`

**URL:** https://www.superbancos.gob.ec/estadisticas/portalestudios/capcol-bancos/
**Fuente:** Superintendencia de Bancos
**Periodicidad:** Mensual (archivos anuales desde 2014)
**Datos:** Captaciones (depósitos) y colocaciones (cartera) de bancos privados — Banca Privada, por entidad, provincia y subtipo de crédito.

```bash
cd src/captaciones_financiero_privado
python main.py                          # descarga + ETL (2014 al año actual)
python main.py --start 2021 --end 2024  # rango específico
python main.py --download-only          # solo descarga ZIPs y extrae Excels
python main.py --etl-only               # ETL sobre Excels ya en disco
python main.py --mode depositos         # solo captaciones
python main.py --mode cartera           # solo colocaciones
```

**Tablas:**

| Tabla | Descripción |
|---|---|
| `captaciones_privadas` | Depósitos de bancos privados — saldo, número de clientes/cuentas, tipo de depósito, por entidad y período |
| `cartera_privadas` | Cartera de crédito de bancos privados — por vencer / no devenga / vencida / total, por tipo de colocación y entidad |

**Tablas de staging (intermedias):** `stg_captaciones_privadas`, `stg_cartera_privadas`

**Notas:**
- El bot usa **Playwright** para navegar el portal OneDrive de Superbancos (requiere `playwright install chromium`).
- Detecta automáticamente si los archivos están en la carpeta del año directamente (Variante A) o en subcarpetas (Variante B).
- Variantes de Excel según año: formato reporte (2014–2020, solo `por_vencer`) y formato tabular (2021+, 4 métricas).
- Deduplicación por hash SHA-256; re-ejecutar es idempotente.

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

### `recaudacion_mensual`

**URL:** https://descargas.sri.gob.ec/download/datosAbiertos/sri_recaudacion_{YEAR}.csv
**Fuente:** Servicio de Rentas Internas (SRI)
**Periodicidad:** Anual (archivo por año), datos mensuales internos — 2017 al año actual
**Datos:** Recaudación tributaria mensual por impuesto, tipo de contribuyente, provincia y cantón.

```bash
cd src/recaudacion_mensual
python main.py                  # descarga + ETL (2017 al año actual)
python main.py --download-only  # solo descarga
python main.py --etl-only       # ETL sobre archivos ya en disco
python main.py --start 2022     # desde 2022
```

**Tabla `recaudacion_mensual_provincial`:**

| Columna | Tipo | Descripción |
|---|---|---|
| `anio` | INT | Año del dato |
| `mes_num` | TINYINT | Número de mes (1-12) — índice clustered |
| `mes` | NVARCHAR(30) | Nombre del mes ("Enero", etc.) |
| `grupo_impuesto` | NVARCHAR(300) | Grupo del impuesto |
| `subgrupo_impuesto` | NVARCHAR(300) | Subgrupo del impuesto |
| `impuesto` | NVARCHAR(500) | Nombre del impuesto |
| `gran_contribuyente` | NVARCHAR(10) | Indicador gran contribuyente (S/N) |
| `codigo_opera_familia` | NVARCHAR(100) | Código operativo de familia |
| `tipo_contribuyente` | NVARCHAR(200) | Tipo de contribuyente |
| `provincia` | NVARCHAR(100) | Provincia |
| `canton` | NVARCHAR(200) | Cantón |
| `valor_recaudado` | FLOAT | Monto recaudado en USD |

**Notas:**
- Archivos CSV pipe-separated (`|`); encoding `utf-8-sig` (2017) y `latin-1` (2018+).
- `VALOR_RECAUDADO` usa coma como separador decimal: `"88123,17"` → `88123.17`.
- Deduplicación por `(anio, mes_num)`: meses ya cargados se omiten sin releer.
- Índice clustered en `(anio, mes_num)` para ordenamiento calendario natural.
- ~600 000–700 000 filas por año; lectura en chunks de 50 000 filas.

---

### `mutualistas`

**URL:** https://estadisticas.seps.gob.ec/index.php/estadisticas-sfps/#cartera_credito
**Fuente:** Superintendencia de Economía Popular y Solidaria (SEPS)
**Periodicidad:** Mensual (archivos anuales actualizados durante el año)
**Datos:** Captaciones y colocaciones de mutualistas y cooperativas (segmentos 1, 2, 3) — 2017 al año actual.

```bash
cd src/mutualistas
python main.py                   # descarga + ETL completo (2017 al año actual)
python main.py --download-only   # solo descarga ZIPs
python main.py --etl-only        # ETL sobre ZIPs ya en disco
python main.py --start 2022      # desde 2022
python main.py --captaciones     # solo flujo de captaciones
python main.py --colocaciones    # solo flujo de colocaciones
```

**Formatos de archivo aceptados:** `.xlsm`, `.xlsx`, `.xltm`, `.txt`, `.csv` — todos los loaders detectan el formato automáticamente y ajustan parser, encoding y separador.

#### Captaciones (3 tablas)

| Tabla | Fuente | Descripción |
|---|---|---|
| `mutualistas_captaciones` | Reportes `*_Mut*` | Captaciones de asociaciones mutualistas |
| `mutualistas_captaciones_sectores` | Reportes `*_S1/S2/S3*` | Captaciones por segmento de cooperativas + columna `sector` (1/2/3) |
| `mutualistas_captaciones_bruto` | Bases anuales | Base granular: tipo persona, parroquia, banda maduración, sexo, rango edad, nivel instrucción |

Descargadores: `bot.py` — ZIP de reportes por año (desde 2020 individual; 2015–2019 en ZIP histórico) y ZIP de bases por año (desde 2018 individual; pre-2018 en ZIP histórico).

#### Colocaciones (8 tablas)

| Tabla | Fuente | Descripción |
|---|---|---|
| `mutualistas_colocaciones_volumen_credito` | Volumen mensual `*_Mut*` | Volumen de crédito mensual — mutualistas |
| `mutualistas_colocaciones_volumen_credito_sectores` | Volumen mensual `*_S1/S2/S3*` | Volumen de crédito mensual — cooperativas por segmento |
| `mutualistas_colocaciones` | Colocaciones `*_Mut*` | Colocaciones mensuales — mutualistas |
| `mutualistas_colocaciones_sectores` | Colocaciones `*_S1/S2/S3*` | Colocaciones mensuales — cooperativas por segmento |
| `mutualistas_colocaciones_volumen_credito_bruto` | Bases TXT volumen | Base granular de volumen: actividad CIIU, provincia, tipo crédito, sexo, rango monto/plazo |
| `mutualistas_colocaciones_mensual_bruto` | Bases TXT Deflate64 (~2.8 GB) | Base granular de colocaciones: saldo por vencer/vencido/no devenga por segmento, CIIU y parroquia |
| `mutualistas_colocaciones_tarjetas_con_forma_pago` | Tarjetas ZIP — archivo "con" | Cartera de tarjetas de crédito por forma de pago, sexo, instrucción, rango edad |
| `mutualistas_colocaciones_tarjetas_sin_forma_pago` | Tarjetas ZIP — archivo "sin" | Cartera de tarjetas de crédito por sexo, instrucción, rango edad; número de tarjetas y tarjetahabientes |

Descargador: `bot_colocaciones.py` — 5 tipos de ZIP anuales, cada uno con ZIP histórico previo al primer año individual.

**Notas técnicas:**
- Detección de cambios via **ETag HTTP** (sidecar `.etag`); archivos históricos se omiten si ya están en disco.
- Archivos `col_bruto` usan compresión **Deflate64** (compress_type=9); requiere `pip install inflate64`.
- Hoja Excel detectada automáticamente: prueba nombre conocido → keyword → primera hoja con datos.
- ZIP "anterior" cubre años pre-individuales (pre-2020 captaciones, pre-2017 col_bruto, etc.).
- Deduplicación por **hash SHA-256** por registro; re-ejecutar no duplica datos.

---

## Pendiente de implementar

Los siguientes módulos tienen carpeta con stubs pero sin bot ni loader funcionales:

| Módulo | Fuente | Periodicidad | Descripción |
|---|---|---|---|
| `pib_nominal` | BCE | Trimestral | PIB nominal total |
| `pib_nominal_industria` | BCE | Trimestral | PIB nominal por industria |
| `pib_industria` | BCE | Trimestral | PIB por industria (variación) |
| `ventas_actividad_economica_sri` | SRI | Mensual | Ventas por actividad económica |

---

## Dependencias

```
pandas          manipulación de DataFrames
openpyxl        lectura de archivos .xlsx / .xlsm
xlrd            lectura de archivos .xls (formato Excel 97-2003)
sqlalchemy      ORM y engine para SQL Server
pyodbc          driver ODBC para SQL Server
playwright      automatización del browser (portales con JS)
requests        descarga directa de archivos y APIs JSON
inflate64       descompresión Deflate64 (requerido para mutualistas col_bruto)
```

> **Nota:** `inflate64` se instala con `pip install inflate64`. Si no está instalado, el loader de `mutualistas_colocaciones_mensual_bruto` se omite automáticamente con un aviso, sin afectar al resto del pipeline.

---

## Convenciones de implementación

- **Deduplicación:** cada fila tiene un hash SHA-256. La carga es idempotente — re-ejecutar no duplica datos.
- **PK no clusterizada + índice clustered:** `BIGINT IDENTITY` como PK física nonclustered; el índice clustered se define por las columnas de consulta más frecuentes (fecha, año, indicador, etc.).
- **Skip inteligente:** el bot verifica si el archivo ya está en disco (o si el tamaño remoto coincide) antes de descargar; el loader verifica hashes antes de insertar.
- **Tolerancia a cambios de formato:** los parsers localizan datos por etiqueta de texto o keyword en cabeceras, no por número de fila fijo, para tolerar reestructuraciones anuales de BCE/INEC.
- **Encoding:** los JSON y Excel del BCE se decodifican forzando UTF-8 para manejar correctamente caracteres como `ñ`, `á`, `é`, etc.
