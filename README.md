# MPA PX - Automatización de Mensajería de Cobranza

Script de automatización para el envío de mensajes de cobranza a clientes con acuerdos de pago activos (MPA), desarrollado en Python.

## ¿Qué hace?

El proceso corre en dos bloques:

- **Bloque 1:** Se conecta a MySQL, extrae los clientes activos, los clasifica por tipo de mensaje (preventivo, vencimiento, atraso) y genera los CSVs del día.
- **Bloque 2:** Lee los CSVs generados, muestra un resumen, pide confirmación y envía los mensajes automáticamente a través del CRM usando Selenium.

## Tecnologías

- Python (pandas, mysql-connector, selenium, dotenv, openpyxl)
- MySQL
- Selenium WebDriver

## Configuración

Crear un archivo `.env` basado en `.env.example` con las credenciales correspondientes.
