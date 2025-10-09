import os
import requests
import time
import random
from datetime import datetime
from telegram import Bot
from dotenv import load_dotenv

# --- Cargar variables ---
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HF_TOKEN = os.getenv("HF_TOKEN")

bot = Bot(token=TELEGRAM_TOKEN)

# --- Lista de recordatorios ---
reminders = [
    "Revisar informe semanal de producción",
    "Verificar stock de materia prima",
    "Enviar reporte de mantenimiento",
    "Preparar reunión del lunes con jefatura",
]

# --- Modelos recomendados ---
AI_MODELS = [
    "meta-llama/Meta-Llama-3-8B-Instruct",
    "mistralai/Mistral-7B-Instruct-v0.3",
    "tiiuae/falcon-7b-instruct",
]

# --- Función IA con manejo de errores y reintentos ---
def ai_generate_message(reminders, max_retries=3):
    model = random.choice(AI_MODELS)
    today = datetime.now().strftime("%A %d de %B de %Y")
    
    prompt = (
        f"Eres un asistente de productividad experto en gestión del tiempo. "
        f"Hoy es {today}. A partir de esta lista de tareas: {reminders}, realiza lo siguiente:\n\n"
        "1. Reescribe cada tarea en español de forma breve, clara y motivante.\n"
        "2. Ordena las tareas por prioridad lógica (alta, media, baja).\n"
        "3. Agrega un consejo breve de enfoque o energía para el día.\n"
        "4. Incluye un emoji apropiado junto a cada tarea.\n"
        "5. Responde en formato atractivo tipo mensaje de coach.\n"
    )
    
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 250,
            "temperature": 0.8,
            "top_p": 0.9,
            "do_sample": True,
            "return_full_text": False
        }
    }

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                f"https://api-inference.huggingface.co/models/{model}",
                headers=headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code != 200:
                print(f"⚠️ Intento {attempt}: Error HTTP {response.status_code}: {response.text[:200]}")
                time.sleep(attempt * 2)  # backoff exponencial
                continue

            try:
                result = response.json()
            except Exception as e:
                print(f"⚠️ Intento {attempt}: No se pudo decodificar JSON: {e}\nRespuesta: {response.text[:200]}")
                time.sleep(attempt * 2)
                continue

            if isinstance(result, list) and "generated_text" in result[0]:
                return result[0]["generated_text"].strip()
            else:
                print(f"⚠️ Intento {attempt}: Respuesta inesperada: {result}")
                time.sleep(attempt * 2)
                continue

        except requests.exceptions.RequestException as e:
            print(f"🚨 Intento {attempt}: Error de conexión o timeout: {e}")
            time.sleep(attempt * 2)

    return "⚠️ No se pudo generar mensaje con IA después de varios intentos."

# --- Función opcional: resumen motivacional del día ---
def ai_generate_summary(reminders):
    prompt = (
        f"Resume en una frase positiva el impacto de completar estas tareas: {reminders}. "
        "Usa tono motivador y humano en español."
    )
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    try:
        response = requests.post(
            "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3",
            headers=headers,
            json={"inputs": prompt},
            timeout=30
        )
        result = response.json()
        if isinstance(result, list) and "generated_text" in result[0]:
            return result[0]["generated_text"].strip()
    except Exception as e:
        print(f"⚠️ Error generando resumen: {e}")
    return "Hoy es un gran día para avanzar con energía. 💪"

# --- Enviar recordatorio a Telegram ---
def send_reminder():
    today = datetime.now().strftime("%d-%m-%Y")
    ai_message = ai_generate_message(reminders)
    ai_summary = ai_generate_summary(reminders)

    final_message = (
        f"📅 *Recordatorios del día* ({today})\n\n"
        f"{ai_message}\n\n"
        f"🌟 *Resumen del día:* {ai_summary}"
    )

    bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=final_message,
        parse_mode="Markdown"
    )

# --- Ejecución principal ---
if __name__ == "__main__":
    send_reminder()
