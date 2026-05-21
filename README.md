# data_verso

Pipeline de ETL para indicadores económicos y financieros de Ecuador. Descarga datos desde portales públicos (Superbancos, BCE, SRI, INEC, SEPS) y los carga en una base de datos SQL Server local.

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
│   ├── normalizer.py           # Funciones de limpieza de texto y números
│   └── ciiu.py                 # Mapeo CIIU v4.0 Ecuador (código → descripción + nivel)
│
├── src/
│   ├── riesgo_pais/                      ✓ implementado
│   ├── pib_per_capita_nominal/           ✓ implementado
│   ├── tipo_de_cambio/                   ✓ implementado
│   ├── reservas_internacionales/         ✓ implementado
│   ├── depositos_gobierno_bce/           ✓ implementado
│   ├── inflacion_ecuador/                ✓ implementado
│   ├── empleo/                           ✓ implementado
│   ├── captaciones_financiero_publico/   ✓ implementado
│   ├── captaciones_financiero_privado/   ✓ implementado
│   ├── recaudacion_mensual/              ✓ implementado
│   ├── mutualistas/                      ✓ implementado
│   ├── pib_nominal_industria/            ✓ implementado
│   └── ventas_actividad_economica_sri/   ✓ implementado
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

### Ejecución del pipeline completo

```bash
# Desde la raíz del proyecto
python main.py                        # todos los módulos en orden
python main.py -m ventas pib          # solo módulos que contienen "ventas" o "pib"
python main.py --list                 # muestra los módulos disponibles
python main.py --download-only        # solo descarga en todos los módulos
python main.py --etl-only             # solo ETL en todos los módulos
```

---

## Fuentes implementadas

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

**No requiere Playwright** — el BCE expone los datos en un endpoint JSON directo.

**Tabla `riesgo_pais`:**

| Columna | Tipo | Descripción |
|---|---|---|
| `fecha` | DATE | Fecha del dato (índice clustered) |
| `valor_riesgo_pais` | FLOAT | EMBI en puntos básicos |
| `fecha_actualizacion` | DATE | Fecha de última actualización en BCE |
| `hash_registro` | NVARCHAR(64) | SHA-256 para deduplicación |

---

### `pib_per_capita_nominal`

**Fuente:** Banco Central del Ecuador — Excel BCE
**Periodicidad:** Anual

**Tabla `pib_per_capita_nominal`**

---

### `tipo_de_cambio`

**Fuente:** Banco Central del Ecuador — Excel BCE
**Periodicidad:** Mensual

**Tabla `tipo_de_cambio`**

---

### `reservas_internacionales`

**URL:** https://contenido.bce.fin.ec/documentos/informacioneconomica/MonetarioFinanciero/ix_ReservasInternacionales.html
**Fuente:** Banco Central del Ecuador
**Periodicidad:** Mensual (desde 2000) y Anual (desde 2000)
**Datos:** Reservas internacionales del Ecuador — posición neta en divisas, oro, DEG, posición FMI, ALADI, SUCRE y total RI.

```bash
cd src/reservas_internacionales
python main.py
python main.py --download-only
python main.py --etl-only
```

**Tablas:**

| Tabla | Descripción |
|---|---|
| `reservas_internacionales_anual` | Una fila por (anio, indicador) — 10 indicadores × ~26 años |
| `reservas_internacionales_mensual` | Una fila por (anio, mes_num, mes, indicador) — ~316 meses |

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

| Tabla | Hoja fuente | Descripción |
|---|---|---|
| `depositos_gobierno_ims1` | IMS1 | Oferta monetaria — 24 indicadores por (año, mes) |
| `depositos_gobierno_ims1_1` | IMS1.1 | M1 y liquidez total M2 — 15 indicadores |
| `depositos_gobierno_ims2` | IMS2 | Activos/pasivos por sector |
| `depositos_gobierno_ims2_2` | IMS2 (2) | Segunda parte IMS2 |
| `depositos_gobierno_ims3` | IMS3 | Balance del Banco Central |
| `depositos_gobierno_ims4` | IMS4 | Balance sectorial BCE — depósitos del Gobierno Central |
| `depositos_gobierno_ims5` | IMS5 | Otras sociedades de depósito |
| `depositos_gobierno_ims6` | IMS6 | Sector externo |
| `depositos_gobierno_ims7` | IMS7 | Tasas de interés |

---

### `inflacion_ecuador`

**URL:** https://www.ecuadorencifras.gob.ec/inflacion/
**Fuente:** INEC — Índice de Precios al Consumidor (IPC)
**Periodicidad:** Mensual (serie histórica desde 1969)

```bash
cd src/inflacion_ecuador
python main.py
python main.py --download-only
python main.py --etl-only
```

**Tablas:**

| Tabla | Descripción |
|---|---|
| `inflacion_ecuador_variacion_mensual` | Variación mensual del IPC por división CCIF |
| `inflacion_ecuador_variacion_anual` | Variación anual del IPC por división CCIF |
| `inflacion_ecuador_indicadores_variacion_mensual` | Indicadores mensuales (general, alimentos, bienes, servicios) |
| `inflacion_ecuador_indicadores_variacion_anual` | Indicadores anuales |
| `inflacion_ecuador_series_incidencias_mensual` | Incidencias mensuales por división CCIF |
| `inflacion_ecuador_series_incidencias_anual` | Incidencias anuales por división CCIF |
| `inflacion_ecuador_series_ipc_mensual` | Variación mensual por región/ciudad y CCIF |
| `inflacion_ecuador_series_ipc_anual` | Variación anual por región/ciudad y CCIF |

---

### `empleo`

**URL (trimestral):** https://www.ecuadorencifras.gob.ec/enemdu-trimestral/
**URL (mensual):** https://www.ecuadorencifras.gob.ec/estadisticas-laborales-enemdu/
**Fuente:** INEC — ENEMDU
**Periodicidad:** Trimestral (desde 2020) y Mensual (histórico desde 2007)

```bash
cd src/empleo
python main.py
python main.py --tipo trimestral
python main.py --tipo mensual --start 2022
```

**Tablas:**

| Tabla | Descripción |
|---|---|
| `empleo_poblacion` | PEA, PEI, PET, ocupados, desocupados — desagregados por área, edad, sexo, etnia |
| `empleo_tasas` | Tasas de empleo, desempleo, subempleo, brecha |
| `empleo_caracterizacion` | Distribución de empleados plenos, subempleados, desocupados por categoría |
| `empleo_sectorizacion` | Empleo por sector económico (formal, informal, doméstico, etc.) |

---

### `captaciones_financiero_publico`

**URL:** https://www.superbancos.gob.ec/estadisticas/portalestudios/capcol-instituciones-publicas/
**Fuente:** Superintendencia de Bancos
**Periodicidad:** Mensual

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

```bash
cd src/captaciones_financiero_privado
python main.py
python main.py --start 2021 --end 2024
python main.py --download-only
python main.py --etl-only
python main.py --mode depositos
python main.py --mode cartera
```

**Tablas:**

| Tabla | Descripción |
|---|---|
| `captaciones_privadas` | Depósitos de bancos privados — saldo, número de clientes/cuentas, tipo de depósito, por entidad y período |
| `cartera_privadas` | Cartera de crédito de bancos privados — por vencer / no devenga / vencida / total |

**Notas:**
- El bot usa **Playwright** para navegar el portal OneDrive de Superbancos.
- Deduplicación por hash SHA-256; re-ejecutar es idempotente.

---

### `recaudacion_mensual`

**URL:** https://descargas.sri.gob.ec/download/datosAbiertos/sri_recaudacion_{YEAR}.csv
**Fuente:** Servicio de Rentas Internas (SRI)
**Periodicidad:** Anual (archivo por año), datos mensuales — 2017 al año actual

```bash
cd src/recaudacion_mensual
python main.py
python main.py --download-only
python main.py --etl-only
python main.py --start 2022
```

**Tabla `recaudacion_mensual_provincial`:**

| Columna | Tipo | Descripción |
|---|---|---|
| `anio` | INT | Año del dato |
| `mes_num` | TINYINT | Número de mes (1-12) |
| `mes` | NVARCHAR(30) | Nombre del mes |
| `grupo_impuesto` | NVARCHAR(300) | Grupo del impuesto |
| `subgrupo_impuesto` | NVARCHAR(300) | Subgrupo del impuesto |
| `impuesto` | NVARCHAR(500) | Nombre del impuesto |
| `tipo_contribuyente` | NVARCHAR(200) | Tipo de contribuyente |
| `provincia` | NVARCHAR(100) | Provincia |
| `canton` | NVARCHAR(200) | Cantón |
| `valor_recaudado` | FLOAT | Monto recaudado en USD |

**Notas:**
- ~600 000–700 000 filas por año; lectura en chunks de 50 000.
- Encoding `utf-8-sig` (2017) y `latin-1` (2018+).

---

### `mutualistas`

**URL:** https://estadisticas.seps.gob.ec/index.php/estadisticas-sfps/#cartera_credito
**Fuente:** Superintendencia de Economía Popular y Solidaria (SEPS)
**Periodicidad:** Mensual (archivos anuales actualizados durante el año)
**Datos:** Captaciones y colocaciones de mutualistas y cooperativas (segmentos 1, 2, 3) — 2017 al año actual.

```bash
cd src/mutualistas
python main.py
python main.py --download-only
python main.py --etl-only
python main.py --start 2022
python main.py --captaciones
python main.py --colocaciones
```

#### Captaciones (3 tablas)

| Tabla | Descripción |
|---|---|
| `mutualistas_captaciones` | Captaciones de asociaciones mutualistas |
| `mutualistas_captaciones_sectores` | Captaciones por segmento de cooperativas + columna `sector` (1/2/3) |
| `mutualistas_captaciones_bruto` | Base granular: tipo persona, parroquia, banda maduración, sexo, rango edad |

#### Colocaciones (8 tablas)

| Tabla | Descripción |
|---|---|
| `mutualistas_colocaciones_volumen_credito` | Volumen de crédito mensual — mutualistas |
| `mutualistas_colocaciones_volumen_credito_sectores` | Volumen de crédito mensual — cooperativas por segmento |
| `mutualistas_colocaciones` | Colocaciones mensuales — mutualistas |
| `mutualistas_colocaciones_sectores` | Colocaciones mensuales — cooperativas por segmento |
| `mutualistas_colocaciones_volumen_credito_bruto` | Base granular de volumen: CIIU, provincia, tipo crédito, sexo |
| `mutualistas_colocaciones_mensual_bruto` | Base granular de colocaciones (compresión Deflate64, ~2.8 GB) |
| `mutualistas_colocaciones_tarjetas_con_forma_pago` | Cartera de tarjetas por forma de pago, sexo, instrucción, rango edad |
| `mutualistas_colocaciones_tarjetas_sin_forma_pago` | Cartera de tarjetas por sexo, instrucción, rango edad |

**Notas:**
- Detección de cambios via **ETag HTTP**; archivos históricos se omiten si ya están en disco.
- Archivos `col_bruto` usan compresión **Deflate64** (requiere `pip install inflate64`).
- Deduplicación por **hash SHA-256**; re-ejecutar no duplica datos.

---

### `pib_nominal_industria`

**URL:** https://contenido.bce.fin.ec/documentos/informacioneconomica/cuentasnacionales/ix_cuentasnacionalestrimestrales.html
**Fuente:** Banco Central del Ecuador — Cuentas Nacionales Trimestrales
**Periodicidad:** Trimestral (archivos anuales, desde 2023)
**Datos:** Valor Agregado Bruto (VAB) por industrias — datos brutos y ajustados de estacionalidad, en precios corrientes, precios encadenados e índices de volumen.

```bash
cd src/pib_nominal_industria
python main.py
python main.py --download-only
python main.py --etl-only
python main.py --start 2024
```

**Tablas:**

| Tabla | Descripción |
|---|---|
| `pib_nominal_industria_bruto` | Hojas de datos brutos — una fila por (anio, trimestre, industria, tipo_indice) |
| `pib_nominal_industria` | Hojas de datos ajustados de estacionalidad — misma estructura |

**Columna `tipo_indice`** — indica el tipo de medición:

| Valor | Descripción |
|---|---|
| `Precios Corrientes` | Valores a precios corrientes del período |
| `Precios Encadenados` | Valores encadenados en dólares |
| `Índices de Volumen Encadenados, 2018=100` | Índice de volumen con base 2018 |
| `... Datos Ajustados de Estacionalidad` | Versiones SA de los anteriores |
| `... Variación Interanual` / `Variación Intertrimestral` | Tasas de variación |

**Notas:**
- El bot descarga archivos `vab_*.xlsx` del portal BCE usando `requests`.
- Detección de cambios via ETag para archivos recientes (último año y anterior).
- La lectura del Excel usa `openpyxl` con `data_only=False` (las fórmulas no tienen valores en caché).

---

### `ventas_actividad_economica_sri`

**URL:** https://srienlinea.sri.gob.ec/saiku-ui/
**Fuente:** SRI Ecuador — Saiku OLAP REST API (srienlinea.sri.gob.ec/saiku/)
**Periodicidad:** Anual (2020-presente)
**Datos:** Ventas e ingresos por actividad económica CIIU para declaraciones 101, 103 y 104.

```bash
cd src/ventas_actividad_economica_sri
python main.py                  # consulta API + carga BD (desde 2018)
python main.py --download-only  # solo consulta API, sin cargar BD
python main.py --start 2022     # desde 2022
```

**Descarga automática** — el bot consulta la API REST de Saiku OLAP directamente (sin Playwright). No requiere intervención manual.

**Tablas:**

| Tabla | Declaración | Métrica | Código |
|---|---|---|---|
| `ventas_ingresos_101` | Form 101 | Total Ingresos | (699) |
| `ventas_vnl12_101` | Form 101 | Ventas Netas Locales 12% | (601) |
| `ventas_vnl0_101` | Form 101 | Ventas Netas Locales 0% | (602) |
| `ventas_exportaciones_104` | Form 104 | Total Ventas y Exportaciones | (419) |
| `ventas_dependencia_103` | Form 103 | Retenciones Relación de Dependencia | (270) |
| `ventas_honorarios_103` | Form 103 | Honorarios Profesionales | (320) |

**Esquema de cada tabla:**

| Columna | Tipo | Descripción |
|---|---|---|
| `codigo_ciiu` | NVARCHAR(20) | Código de actividad económica CIIU v4.0 |
| `descripcion` | NVARCHAR(MAX) | Descripción de la actividad (desde `utils/ciiu.py`) |
| `nivel_ciiu` | NVARCHAR(20) | Nivel jerárquico: SECCION / GRUPO / SUBGRUPO / CLASE / SUBCLASE / ACTIVIDAD |
| `anio` | SMALLINT | Año fiscal de la declaración |
| `valor` | FLOAT | Monto en USD |
| `hash_registro` | NVARCHAR(64) | SHA-256 para deduplicación |

**Notas:**
- La API Saiku es pública pero requiere sesión Spring Security (credenciales por defecto de Saiku CE).
- Los datos disponibles parten desde 2020 (límite del sistema SRI).
- Las columnas `descripcion` y `nivel_ciiu` se enriquecen desde `utils/ciiu.py` usando el Clasificador Industrial Internacional Uniforme v4.0.
- ~62 000 registros en total por carga inicial; idempotente por hash.

---

## Utilitarios (`utils/`)

### `base_engine.py`
Crea y devuelve el engine de SQLAlchemy conectado a SQL Server con autenticación Windows.

### `normalizer.py`
Funciones de limpieza y normalización de texto y valores numéricos usadas por múltiples loaders.

### `ciiu.py`
Lee la hoja `CIIU` del archivo de referencia (`CIUS Para ventas por actividad economicaFInal 2.xls`) y construye un diccionario `{codigo → (descripcion, nivel)}` con los 3 261 códigos CIIU v4.0 Ecuador.

```python
from utils.ciiu import get_map

ciiu = get_map()
desc, nivel = ciiu.get("A011111", (None, None))
# → ("CULTIVO DE TRIGO.", "ACTIVIDAD")
```

El resultado se cachea en memoria (`lru_cache`) — solo se lee el archivo una vez por proceso.

---

## Dependencias

```
pandas          manipulación de DataFrames
numpy           operaciones numéricas (usado por mutualistas y recaudacion)
openpyxl        lectura de archivos .xlsx / .xlsm
xlrd            lectura de archivos .xls (formato Excel 97-2003)
sqlalchemy      ORM y engine para SQL Server
pyodbc          driver ODBC para SQL Server
playwright      automatización del browser (portales con JS: Superbancos, INEC, BCE)
requests        descarga directa de archivos y APIs REST (BCE, SRI Saiku, INEC)
inflate64       descompresión Deflate64 (requerido para mutualistas col_bruto)
```

> **Nota:** `inflate64` se instala con `pip install inflate64`. Si no está instalado, el loader de `mutualistas_colocaciones_mensual_bruto` se omite automáticamente con un aviso, sin afectar al resto del pipeline.

---

## Convenciones de implementación

- **Deduplicación:** cada fila tiene un hash SHA-256. La carga es idempotente — re-ejecutar no duplica datos.
- **PK no clusterizada + índice clustered:** `BIGINT IDENTITY` como PK física nonclustered; el índice clustered se define por las columnas de consulta más frecuentes (fecha, año, indicador, etc.).
- **Skip inteligente:** el bot verifica si el archivo ya está en disco (o el ETag remoto coincide) antes de descargar; el loader verifica hashes antes de insertar.
- **Tolerancia a cambios de formato:** los parsers localizan datos por etiqueta de texto o keyword en cabeceras, no por número de fila fijo, para tolerar reestructuraciones anuales.
- **Encoding:** los archivos del BCE/SRI/INEC se decodifican forzando UTF-8 o cp1252 según la fuente para manejar correctamente caracteres como `ñ`, `á`, `é`, etc.
