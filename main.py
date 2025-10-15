# =========================================================
# 🧠 PROYECTO: Generador de Desafíos Motivacionales con IA
# Rol conceptual: Diseño de información + IA aplicada a bienestar
# Autor: Francisco Lodi
# Fecha: 2025
# =========================================================

# --- Dependencias base ---
from huggingface_hub import InferenceClient
from telegram import Bot
from datetime import datetime
import os
import time

# --- Cargar credenciales seguras desde entorno ---
HF_TOKEN = os.getenv("HF_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- Inicializar clientes ---
client = InferenceClient(api_key=HF_TOKEN)
bot = Bot(token=TELEGRAM_TOKEN)

# =========================================================
# 🔹 ESTRUCTURA DE DATOS: Desafíos
# Pensado como un "pool semántico" que puede expandirse o conectarse con APIs
# =========================================================
DESAFIOS = [
    "CrossFit: haz un circuito de 20 minutos con salto, cuerda y burpees",
    "Alimentación: prepara una comida rica en proteínas y vegetales verdes",
    "Bienestar: dedica 10 minutos a respirar y estirar al despertar",
    "Mindfulness: camina sin música, concentrado en tu respiración",
]

# =========================================================
# 🔹 FUNCIÓN PRINCIPAL: Generador de desafío motivador
# Centrada en claridad, tono y experiencia emocional
# =========================================================
def generar_desafio(desafio):
    """Crea una versión inspiradora y concreta de un desafío diario usando IA."""
    
    prompt = (
        f"Reformula el siguiente desafío diario en un mensaje motivacional breve y poderoso: '{desafio}'. "
        "Debe sonar enérgico, positivo, en español y orientado al bienestar físico y mental."
    )

    response = client.chat_completion(
        model="mistralai/Mistral-7B-Instruct-v0.2",
        messages=[
            {"role": "system", "content": "Eres un coach inspirador experto en fitness, salud y motivación personal."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=120,
        temperature=0.9,
    )

    # Manejo de salida seguro
    return response.choices[0].message["content"].strip()

# =========================================================
# 🔹 CANAL DE ENTREGA: Telegram
# Diseño simple, legible y escalable (se puede conectar a Slack o WhatsApp)
# =========================================================
def enviar_a_telegram(mensaje):
    """Envía el mensaje generado a un canal de Telegram."""
    timestamp = datetime.now().strftime('%H:%M:%S')
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"⏰ {timestamp}\n{mensaje}")
    print(f"[{timestamp}] {mensaje}")

# =========================================================
# 🔹 LOOP PRINCIPAL
# Con un delay humano, simulando ritmo natural de comunicación
# =========================================================
def ejecutar_ciclo_desafios():
    for desafio in DESAFIOS:
        mensaje = generar_desafio(desafio)
        enviar_a_telegram(mensaje)
        time.sleep(3)  # Pausa entre envíos (más natural)

# =========================================================
# 🚀 EJECUCIÓN
# =========================================================
if __name__ == "__main__":
    print("✨ Iniciando ciclo de desafíos motivacionales...")
    ejecutar_ciclo_desafios()
    print("✅ Envío completado.")
