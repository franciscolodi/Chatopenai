# =========================================================
# 🧠 PROYECTO: Generador de desafíos diarios con IA (Groq API)
# =========================================================

from groq import Groq
from telegram import Bot
from datetime import datetime
import os
import time
import json

# --- Credenciales ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- Inicializar clientes ---
client = Groq(api_key=GROQ_API_KEY)
bot = Bot(token=TELEGRAM_TOKEN)


def generar_desafios_diarios():
    prompt = (
        "Genera tres desafíos diarios distintos y concisos en español, uno por categoría: "
        "CrossFit, Alimentación y Bienestar. "
        "Cada desafío debe tener tono sobrio, informativo, científico y pragmático. "
        "Evita frases motivacionales o inspiracionales. "
        "Devuelve **solo** un objeto JSON válido, sin texto adicional, sin explicación ni formato Markdown. "
        "Cada valor debe ser una sola frase breve y clara."
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Eres un especialista en rendimiento humano, nutrición y fisiología. Responde solo con JSON válido."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=200,
        )

        contenido = response.choices[0].message.content.strip()

        # limpiar posibles bloques de Markdown o texto extra
        contenido = contenido.replace("```json", "").replace("```", "").strip()

        desafios = json.loads(contenido)
        return desafios

    except json.JSONDecodeError:
        return {"Error": "Respuesta no es JSON válido", "Contenido": contenido}

    except Exception as e:
        return {"Error": str(e)}



# --- Enviar a Telegram ---
def enviar_a_telegram(mensaje):
    timestamp = datetime.now().strftime('%H:%M:%S')
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"⏰ {timestamp}\n{mensaje}")
    print(f"[{timestamp}] {mensaje}")


# --- Ciclo principal ---
def ejecutar_ciclo_desafios():
    desafios = generar_desafios_diarios()

    if "Error" in desafios:
        enviar_a_telegram(f"⚠️ Error generando desafíos: {desafios['Error']}")
        return

    for categoria, texto in desafios.items():
        mensaje = f"📘 {categoria}:\n{texto}"
        enviar_a_telegram(mensaje)
        time.sleep(5)  # pequeña pausa entre mensajes


# --- Ejecución ---
if __name__ == "__main__":
    print("🧠 Iniciando ciclo de desafíos diarios...")
    ejecutar_ciclo_desafios()
    print("✅ Envío completado.")

