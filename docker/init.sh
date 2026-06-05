#!/bin/bash
# Entrypoint personalizado para SQL Server.
# Al primer arranque: espera a que el motor esté listo y ejecuta init.sql.
# En reinicios siguientes: arranca directamente (sentinel en el volumen).
set -e

# ── Detectar sqlcmd ────────────────────────────────────────────────────────────
if [ -f /opt/mssql-tools18/bin/sqlcmd ]; then
    SQLCMD="/opt/mssql-tools18/bin/sqlcmd -C"
elif [ -f /opt/mssql-tools/bin/sqlcmd ]; then
    SQLCMD="/opt/mssql-tools/bin/sqlcmd"
else
    echo "[init] ERROR: sqlcmd no encontrado en la imagen." && exit 1
fi

# ── Sentinel: si ya fue inicializado, arrancar directo ─────────────────────────
SENTINEL=/var/opt/mssql/.data_verso_initialized
if [ -f "$SENTINEL" ]; then
    echo "[init] Volumen ya inicializado — arrancando SQL Server..."
    exec /opt/mssql/bin/sqlservr
fi

# ── Arrancar SQL Server en background ─────────────────────────────────────────
echo "[init] Arrancando SQL Server en background..."
/opt/mssql/bin/sqlservr &
SQLSERVR_PID=$!

# ── Esperar hasta 3 minutos a que el motor responda ───────────────────────────
echo "[init] Esperando a que SQL Server esté listo..."
READY=0
for i in $(seq 1 60); do
    if $SQLCMD -S localhost -U sa -P "$MSSQL_SA_PASSWORD" \
               -Q "SELECT 1" -b > /dev/null 2>&1; then
        echo "[init] SQL Server listo (intento $i)."
        READY=1
        break
    fi
    echo "[init]   intento $i/60..."
    sleep 3
done

if [ "$READY" -eq 0 ]; then
    echo "[init] ERROR: SQL Server no respondió tras 3 minutos. Abortando."
    kill "$SQLSERVR_PID" 2>/dev/null
    exit 1
fi

# ── Generar SQL con los valores reales del entorno ────────────────────────────
# Nota: las contraseñas no deben contener comillas simples (') ni el signo $.
SQL_TMP=$(mktemp /tmp/init_XXXXXX.sql)
cat > "$SQL_TMP" << SQLEOF
-- ================================================================
-- data_verso — inicialización de base de datos, logins y permisos
-- ================================================================

-- Base de datos
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'${DV_DATABASE}')
BEGIN
    CREATE DATABASE [${DV_DATABASE}];
    PRINT '[init] Base de datos ${DV_DATABASE} creada.';
END
ELSE
    PRINT '[init] Base de datos ${DV_DATABASE} ya existe — omitiendo.';
GO

-- ── Logins (nivel servidor) ───────────────────────────────────────────────────
USE master;
GO

IF NOT EXISTS (SELECT name FROM sys.server_principals WHERE name = N'${DV_ADMIN_USER}')
BEGIN
    CREATE LOGIN [${DV_ADMIN_USER}]
        WITH PASSWORD   = N'${DV_ADMIN_PASSWORD}',
             CHECK_POLICY = OFF;
    PRINT '[init] Login ${DV_ADMIN_USER} creado.';
END
ELSE
    PRINT '[init] Login ${DV_ADMIN_USER} ya existe — omitiendo.';
GO

IF NOT EXISTS (SELECT name FROM sys.server_principals WHERE name = N'${DV_READ_USER}')
BEGIN
    CREATE LOGIN [${DV_READ_USER}]
        WITH PASSWORD   = N'${DV_READ_PASSWORD}',
             CHECK_POLICY = OFF;
    PRINT '[init] Login ${DV_READ_USER} creado.';
END
ELSE
    PRINT '[init] Login ${DV_READ_USER} ya existe — omitiendo.';
GO

-- ── Usuarios y permisos (nivel base de datos) ─────────────────────────────────
USE [${DV_DATABASE}];
GO

IF NOT EXISTS (SELECT name FROM sys.database_principals WHERE name = N'${DV_ADMIN_USER}')
BEGIN
    CREATE USER [${DV_ADMIN_USER}] FOR LOGIN [${DV_ADMIN_USER}];
    PRINT '[init] Usuario ${DV_ADMIN_USER} creado.';
END
GO

IF NOT EXISTS (SELECT name FROM sys.database_principals WHERE name = N'${DV_READ_USER}')
BEGIN
    CREATE USER [${DV_READ_USER}] FOR LOGIN [${DV_READ_USER}];
    PRINT '[init] Usuario ${DV_READ_USER} creado.';
END
GO

-- dv_admin: lectura + escritura + DDL (CREATE TABLE, ALTER TABLE)
-- Necesario para que los loaders ETL puedan crear y alterar tablas.
ALTER ROLE db_datareader ADD MEMBER [${DV_ADMIN_USER}];
ALTER ROLE db_datawriter ADD MEMBER [${DV_ADMIN_USER}];
GRANT CREATE TABLE          TO [${DV_ADMIN_USER}];
GRANT ALTER ON SCHEMA::dbo  TO [${DV_ADMIN_USER}];
PRINT '[init] Permisos DDL+DML asignados a ${DV_ADMIN_USER}.';
GO

-- dv_reader: solo SELECT — para exploración segura desde dbgate u otras apps
ALTER ROLE db_datareader ADD MEMBER [${DV_READ_USER}];
PRINT '[init] Permiso de lectura asignado a ${DV_READ_USER}.';
GO
SQLEOF

echo "[init] Ejecutando script de inicialización..."
$SQLCMD -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -i "$SQL_TMP" -b
rm -f "$SQL_TMP"

# Marcar volumen como inicializado para no repetir en reinicios
touch "$SENTINEL"
echo "[init] Inicialización completada."

# Mantener SQL Server en primer plano
wait "$SQLSERVR_PID"
