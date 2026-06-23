# ============================================================================
# BLOQUE 1 - MPA PX: GENERACIÓN DE CSVs
# Corre la query, clasifica en buckets y guarda los archivos del día.
# Ejecutar cada mañana antes del Bloque 2.
# ============================================================================
import pandas as pd
import mysql.connector
from datetime import date
import os
import logging
from dotenv import load_dotenv
from pathlib import Path

# ════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════════════════════════
load_dotenv()  # carga el .env de la misma carpeta

HOY = date.today()
FECHA_STR = HOY.strftime("%d-%m-%Y")
BASE = os.getenv("BASE_PATH")

CARPETA_PREV = os.path.join(BASE, "Mensajería MPA PX", "PREVENTIVA")
CARPETA_RECP = os.path.join(BASE, "Mensajería MPA PX", "VENCIMIENTO")
CARPETA_ATR  = os.path.join(BASE, "Mensajería MPA PX", "ATRASOS")
CARPETA_LOGS = os.path.join(BASE, "Mensajería MPA PX", "logs")

for carpeta in [CARPETA_PREV, CARPETA_RECP, CARPETA_ATR, CARPETA_LOGS]:
    Path(carpeta).mkdir(parents=True, exist_ok=True)

log_file = os.path.join(CARPETA_LOGS, f"bloque1_{FECHA_STR}.log")
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

HOST_MYSQL     = os.getenv("HOST_MYSQL")
PUERTO_MYSQL   = int(os.getenv("PUERTO_MYSQL"))
USUARIO_MYSQL  = os.getenv("USUARIO_MYSQL")
PASSWORD_MYSQL = os.getenv("PASSWORD_MYSQL")
BASE_MYSQL     = os.getenv("BASE_MYSQL")

logger.info(f"📅 Fecha: {FECHA_STR}")

# ════════════════════════════════════════════════════════════════════════════
# BUCKETS DE ATRASO
# ════════════════════════════════════════════════════════════════════════════
BUCKETS_ATR = {
    "ATR_D01": lambda d: d == 1,
    "ATR_D05": lambda d: d == 5,
    "ATR_D10": lambda d: d == 10,
    "ATR_D15": lambda d: d == 15,
    "ATR_D20": lambda d: d == 20,
    "ATR_D25": lambda d: d == 25,
    "ATR_D26": lambda d: d == 26,
    "ATR_D27": lambda d: d == 27,
    "ATR_D28": lambda d: d == 28,
    "ATR_D29": lambda d: d == 29,
    "ATR_D30": lambda d: d == 30,
}

# ════════════════════════════════════════════════════════════════════════════
# 1. EXTRACCIÓN BD
# ════════════════════════════════════════════════════════════════════════════
logger.info("🔌 Conectando a BD MySQL...")

QUERY = """
WITH CuotaActual AS (
    SELECT
        mpad.multiPaymentAgreementId,
        mpad.paymentAgreementNumber,
        mpad.remainingAmount,
        mpad.dueDate,
        GREATEST(DATEDIFF(CURRENT_DATE(), mpad.dueDate), 0) AS atrasoSubcuota
    FROM MultiPaymentAgreementDetail mpad
),
AtrasoHoy AS (
    SELECT
        cl.clientId,
        COALESCE(DATEDIFF(CURRENT_DATE(), MIN(CASE WHEN i.paymentStatus <> 'FullyPaid' AND DATE(i.dueDate) < CURRENT_DATE() THEN i.dueDate END)), 0) AS atrasoCliOriginal
    FROM Installment i
    INNER JOIN ClientLoan cl ON cl.id = i.loanId
    INNER JOIN Client c ON c.id = cl.clientId AND c.merchantId IS NULL
    INNER JOIN Entity e ON e.id = c.personId
    WHERE cl.operationStatus = 'Normal'
        AND cl.cancellationDate IS NULL
    GROUP BY cl.clientId
),
ResumenValesAcuerdo AS (
    SELECT
        mpap.MultiPaymentAgreementId,
        COUNT(DISTINCT mpap.ProductId) AS Nro_vales_acuerdo,
        MAX(cl.clientId) AS clientId,
        GROUP_CONCAT(mpap.productId SEPARATOR ' | ') AS mpa_loan_id_lista
    FROM MultiPaymentAgreementProduct mpap
    INNER JOIN ClientLoan cl ON cl.id = mpap.productId
    GROUP BY mpap.MultiPaymentAgreementId
)
SELECT
    mpa.id AS mpa_id,
    mpa.status AS estatus_acuerdo,
    e.legalId AS documento,
    c.firstName AS Nombre_Cliente,
    c.firstLastName AS Apellido_cliente,
    c.id AS client_id,
    mpa.paymentAmount AS monto_subcuota,
    DATE(ca.dueDate) AS fecha_vencimiento_cuota,
    DATE(ca.dueDate) - interval 3 day AS fecha_aviso_vencimiento_cuota,
    rva.mpa_loan_id_lista AS mpa_loan_id,
    rva.Nro_vales_acuerdo,
    COALESCE(ah.atrasoCliOriginal, 0) AS atraso_vale_original,
    ca.atrasoSubcuota AS atraso_mpa
FROM MultiPaymentAgreement mpa
INNER JOIN ResumenValesAcuerdo rva ON rva.MultiPaymentAgreementId = mpa.id
INNER JOIN Client c ON c.id = rva.clientId
INNER JOIN Entity e ON e.id = c.personId
LEFT JOIN CuotaActual ca ON ca.multiPaymentAgreementId = mpa.id AND ca.paymentAgreementNumber = mpa.currentPaymentNumber
LEFT JOIN AtrasoHoy ah ON ah.clientId = c.id
WHERE mpa.status IN ('Active');
"""

conn = mysql.connector.connect(
    host=HOST_MYSQL,
    port=PUERTO_MYSQL,
    user=USUARIO_MYSQL,
    password=PASSWORD_MYSQL,
    database=BASE_MYSQL
)
df = pd.read_sql(QUERY, conn)
conn.close()
logger.info(f"✅ {len(df)} registros obtenidos de BD")

if df.empty:
    logger.info("⏭️  Sin datos activos. Fin del proceso.")
else:
    # ════════════════════════════════════════════════════════════════════════
    # 2. CLASIFICACIÓN
    # ════════════════════════════════════════════════════════════════════════
    df["fecha_vencimiento_cuota"]       = pd.to_datetime(df["fecha_vencimiento_cuota"]).dt.date
    df["fecha_aviso_vencimiento_cuota"] = pd.to_datetime(df["fecha_aviso_vencimiento_cuota"]).dt.date

    mask_atr  = df["atraso_mpa"] >= 1
    mask_recp = (df["fecha_vencimiento_cuota"] == HOY) & ~mask_atr
    mask_prev = (df["fecha_aviso_vencimiento_cuota"] == HOY) & ~mask_atr & ~mask_recp

    df_prev = df[mask_prev].copy()
    df_recp = df[mask_recp].copy()
    dfs_atr = {
        nombre: df[df["atraso_mpa"].apply(cond)].copy()
        for nombre, cond in BUCKETS_ATR.items()
    }

    logger.info(f"📊 PREV: {len(df_prev)} | RECP: {len(df_recp)}")
    for nombre, df_b in dfs_atr.items():
        if not df_b.empty:
            logger.info(f"📊 {nombre}: {len(df_b)}")

    # ════════════════════════════════════════════════════════════════════════
    # 3. GENERACIÓN DE CSVs
    # ════════════════════════════════════════════════════════════════════════
    def guardar_csv(df_grupo, carpeta, prefijo):
        if df_grupo.empty:
            return None
        out = pd.DataFrame()
        out["legalId"]     = df_grupo["documento"]
        out["clientName"]  = df_grupo["Nombre_Cliente"]
        out["amount"]      = df_grupo["monto_subcuota"].apply(lambda x: f"{x:.2f}")
        out["dueDate"]     = df_grupo["fecha_vencimiento_cuota"].apply(lambda x: x.strftime("%d/%m/%Y"))
        ruta = os.path.join(carpeta, f"{prefijo} - {FECHA_STR}.csv")
        out.reset_index(drop=True).to_csv(ruta, index=False, encoding="utf-8-sig")
        logger.info(f"✅ {prefijo}: {len(out)} filas → {ruta}")
        return ruta

    guardar_csv(df_prev, CARPETA_PREV, "PREV")
    guardar_csv(df_recp, CARPETA_RECP, "RECP")
    for nombre, df_b in dfs_atr.items():
        guardar_csv(df_b, CARPETA_ATR, nombre)

    logger.info("")
    logger.info("=" * 60)
    logger.info("✅ BLOQUE 1 FINALIZADO")
    logger.info("   Revisá los CSVs y luego corré bloque2_envia_mensajes.py")
    logger.info("=" * 60)

logger.info(f"📁 Log: {log_file}")