# =========================================================
# ✨ PROYECTO: Generador de desafíos motivacionales con IA (Groq API)
# =========================================================

from groq import Groq
from telegram import Bot
from datetime import datetime
import os
import time

# --- Credenciales ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- Inicializar clientes ---
client = Groq(api_key=GROQ_API_KEY)
bot = Bot(token=TELEGRAM_TOKEN)

# --- Lista de desafíos ---
DESAFIOS = [
    "CrossFit: haz un circuito de 20 minutos",
    "Alimentación: prepara una comida saludable rica en proteínas y vegetales",
    "Bienestar: toma 10 minutos para estirarte y respirar profundamente",
]

# --- Generar desafío motivador ---
def generar_desafio(desafio):
    prompt = (
        f"Reformula el siguiente desafío diario en un mensaje motivador, claro y enérgico: '{desafio}'. "
        "Usa tono inspirador y positivo, en español, para alguien que busca mejorar su salud y bienestar."
    )

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",  # También puedes usar "llama3-8b-8192"
        messages=[
            {"role": "system", "content": "Eres un coach experto en motivación, fitness y bienestar."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.9,
        max_tokens=120,
    )

    return response.choices[0].message.content.strip()

# --- Enviar a Telegram ---
def enviar_a_telegram(mensaje):
    timestamp = datetime.now().strftime('%H:%M:%S')
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"⏰ {timestamp}\n{mensaje}")
    print(f"[{timestamp}] {mensaje}")

# --- Loop principal ---
def ejecutar_ciclo_desafios():
    for desafio in DESAFIOS:
        mensaje = generar_desafio(desafio)
        enviar_a_telegram(mensaje)
        time.sleep(3)  # pausa natural entre envíos

# --- Ejecución ---
if __name__ == "__main__":
    print("✨ Iniciando ciclo de desafíos motivacionales...")
    ejecutar_ciclo_desafios()
    print("✅ Envío completado.")

