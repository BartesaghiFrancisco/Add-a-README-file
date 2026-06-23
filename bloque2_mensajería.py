# ============================================================================
# BLOQUE 2 - MPA PX: ENVÍO DE MENSAJES VÍA SELENIUM
# Escanea las carpetas por archivos del día, muestra resumen,
# pide confirmación y procesa cada bucket en el CRM.
# Correr DESPUÉS de bloque1_genera_csvs.py.
# ============================================================================
import os
import logging
from datetime import date
from dotenv import load_dotenv
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# ════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════════════════════════
HOY = date.today()
FECHA_STR = HOY.strftime("%d-%m-%Y")
BASE = r"C:\Users\francisco.bartesaghi\Claude\Projects\MPA Prex"
CREDS_FILE = r"C:\Users\francisco.bartesaghi\OneDrive - Floder SA - RUT 217883680014\DataAnalysis\Fran Bartesaghi\Python\Visual Studio Code\Credenciales.txt"

CARPETA_PREV = os.path.join(BASE, "Mensajería MPA PX", "PREVENTIVA")
CARPETA_RECP = os.path.join(BASE, "Mensajería MPA PX", "VENCIMIENTO")
CARPETA_ATR  = os.path.join(BASE, "Mensajería MPA PX", "ATRASOS")
CARPETA_LOGS = os.path.join(BASE, "Mensajería MPA PX", "logs")

Path(CARPETA_LOGS).mkdir(parents=True, exist_ok=True)

log_file = os.path.join(CARPETA_LOGS, f"bloque2_{FECHA_STR}.log")
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv(CREDS_FILE)
USU_CRM  = os.getenv("USU_CRM")
CSÑA_CRM = os.getenv("CSÑA_CRM")

# ════════════════════════════════════════════════════════════════════════════
# TEMPLATES (ordenados: PREV y RECP primero, luego ATR por día)
# ════════════════════════════════════════════════════════════════════════════
TEMPLATES = {
    "PREV":    "[##CLIENT_NAME##], la fecha de débito de los $[##AMOUNT_TO_PAY##] acordados es el próximo [##DAY_NAME_NAME##], recordá tener cargada tu PREX.",
    "RECP":    "[##CLIENT_NAME##], hoy se debitan los $ [##AMOUNT_TO_PAY##], es importante tener tu PREX cargada. ¡Aprovechá la oportunidad!",
    "ATR_D01": "[##CLIENT_NAME##], ayer no pudimos procesar el débito de los $ [##AMOUNT_TO_PAY##] acordados. Tu compromiso de pago sigue activo; de no regularizar, volvés al cobro original.",
    "ATR_D05": "[##CLIENT_NAME##], aún tenés $[##AMOUNT_TO_PAY##] pendientes de pago. Tu compromiso de pago sigue activo; de no regularizar, volvés al cobro original.",
    "ATR_D10": "[##CLIENT_NAME##], tu compromiso sigue activo. Cargá tu PREX para procesar el débito de $[##AMOUNT_TO_PAY##] a la brevedad.",
    "ATR_D15": "[##CLIENT_NAME##], el pago de $[##AMOUNT_TO_PAY##] sigue pendiente. Recordá que incumplir el compromiso activa el esquema de cobro original.",
    "ATR_D20": "[##CLIENT_NAME##], aún tenés $[##AMOUNT_TO_PAY##] pendientes de pago. Tu compromiso de pago sigue activo; de no regularizar, volvés al cobro original.",
    "ATR_D25": "[##CLIENT_NAME##], tu compromiso sigue activo. Cargá tu PREX para procesar el débito de $[##AMOUNT_TO_PAY##] a la brevedad.",
    "ATR_D26": "[##CLIENT_NAME##], el pago de $[##AMOUNT_TO_PAY##] sigue pendiente. Recordá que incumplir el compromiso activa el esquema de cobro original.",
    "ATR_D27": "[##CLIENT_NAME##], el pago de $[##AMOUNT_TO_PAY##] sigue pendiente. Recordá que incumplir el compromiso activa el esquema de cobro original.",
    "ATR_D28": "[##CLIENT_NAME##], el pago de $[##AMOUNT_TO_PAY##] sigue pendiente. Recordá que incumplir el compromiso activa el esquema de cobro original.",
    "ATR_D29": "[##CLIENT_NAME##], el pago de $[##AMOUNT_TO_PAY##] sigue pendiente. Recordá que incumplir el compromiso activa el esquema de cobro original.",
    "ATR_D30": "[##CLIENT_NAME##], tenés $[##AMOUNT_TO_PAY##]. Si no regularizás, se retoma el esquema de cobro original automáticamente. ¡Hoy es el ultimo día!",
}

# Mapeo: prefijo de archivo → carpeta donde buscarlo
CARPETAS_POR_BUCKET = {
    "PREV":    CARPETA_PREV,
    "RECP":    CARPETA_RECP,
    **{k: CARPETA_ATR for k in TEMPLATES if k.startswith("ATR_")},
}

# ════════════════════════════════════════════════════════════════════════════
# 1. ESCANEAR ARCHIVOS DEL DÍA
# ════════════════════════════════════════════════════════════════════════════
logger.info(f"📅 Fecha: {FECHA_STR}")
logger.info("🔍 Buscando archivos generados hoy...")

archivos_hoy = {}  # bucket → ruta absoluta

for bucket, carpeta in CARPETAS_POR_BUCKET.items():
    nombre_archivo = f"{bucket} - {FECHA_STR}.csv"
    ruta = os.path.join(carpeta, nombre_archivo)
    if os.path.isfile(ruta):
        archivos_hoy[bucket] = ruta

# ════════════════════════════════════════════════════════════════════════════
# 2. RESUMEN Y CONFIRMACIÓN
# ════════════════════════════════════════════════════════════════════════════
print()
print("=" * 60)
print(f"  RESUMEN DE ENVÍOS - {FECHA_STR}")
print("=" * 60)

if not archivos_hoy:
    print("  ⚠️  No se encontraron archivos para hoy.")
    print("       Asegurate de haber corrido bloque1_genera_csvs.py")
    print("=" * 60)
    exit()

import pandas as pd
total_mensajes = 0
for bucket, ruta in archivos_hoy.items():
    df_tmp = pd.read_csv(ruta)
    n = len(df_tmp)
    total_mensajes += n
    print(f"  ✅ {bucket:<12} → {n} mensajes")

print("-" * 60)
print(f"  TOTAL: {total_mensajes} mensajes a enviar")
print("=" * 60)
print()

confirmacion = input("¿Proceder con el envío? (s/n): ").strip().lower()
if confirmacion != "s":
    logger.info("❌ Envío cancelado por el usuario.")
    exit()

logger.info(f"🚀 Confirmado. Procesando {len(archivos_hoy)} bucket(s)...")

# ════════════════════════════════════════════════════════════════════════════
# 3. SELENIUM - ENVÍO
# ════════════════════════════════════════════════════════════════════════════
driver = webdriver.Chrome()
wait = WebDriverWait(driver, 10)
resultados = {}

try:
    # Login (una sola vez)
    driver.get("https://backoffice.internal.paigo.uy/admin/mailing-campaign")
    logger.info("🔐 Haciendo login...")
    wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(USU_CRM)
    driver.find_element(By.NAME, "password").send_keys(CSÑA_CRM)
    driver.find_element(By.XPATH, "//button[contains(text(), 'Ingresar')]").click()
    time.sleep(3)
    logger.info("✅ Login exitoso")

    for bucket, ruta_csv in archivos_hoy.items():
        logger.info(f"\n📤 Procesando {bucket}...")

        # Subir CSV
        file_input = wait.until(EC.presence_of_element_located((By.ID, "react-csv-reader-input")))
        file_input.send_keys(os.path.abspath(ruta_csv))
        time.sleep(1)

        # Marca
        Select(driver.find_element(By.NAME, "select")).select_by_value("PreXtamo")

        # Tipo
        Select(driver.find_element(By.NAME, "type_send")).select_by_value("PUSH_NOTIFICATION")
        time.sleep(1)

        # Título y descripción
        titulo = driver.find_element(By.NAME, "title")
        titulo.clear()
        titulo.send_keys("Recordatorio de pago")

        desc = driver.find_element(By.NAME, "description")
        desc.clear()
        desc.send_keys("Mensajería MPA PX")

        # Template
        body = driver.find_element(By.NAME, "body")
        body.clear()
        body.send_keys(TEMPLATES[bucket])
        logger.info(f"✅ Formulario listo para {bucket}")

        # Enviar
        procesar_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        procesar_btn.click()
        time.sleep(2)
        logger.info(f"✅ {bucket} enviado")
        resultados[bucket] = "SUCCESS"

        # Recargar para el siguiente bucket
        driver.refresh()
        time.sleep(2)

except Exception as e:
    logger.error(f"❌ Error en Selenium: {e}")
    # Registrar el bucket que falló si existe en scope
    try:
        resultados[bucket] = "ERROR"
    except NameError:
        pass
    raise
finally:
    driver.quit()
    logger.info("🔒 Browser cerrado")

# ════════════════════════════════════════════════════════════════════════════
# 4. RESUMEN FINAL
# ════════════════════════════════════════════════════════════════════════════
logger.info("")
logger.info("=" * 60)
logger.info("📊 RESUMEN DE ENVÍO")
logger.info("=" * 60)
for bucket, resultado in resultados.items():
    logger.info(f"  {bucket:<12} → {resultado}")
logger.info("=" * 60)
logger.info(f"✅ BLOQUE 2 FINALIZADO - {FECHA_STR}")
logger.info(f"📁 Log: {log_file}")