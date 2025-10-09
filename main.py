import os
import requests
from datetime import datetime
from telegram import Bot
from dotenv import load_dotenv

# --- Cargar variables ---
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HF_TOKEN = os.getenv("HF_TOKEN")  # token de Hugging Face

bot = Bot(token=TELEGRAM_TOKEN)

# --- Lista de recordatorios ---
reminders = [
    "Revisar informe semanal de producción",
    "Verificar stock de materia prima",
    "Enviar reporte de mantenimiento",
    "Preparar reunión del lunes con jefatura",
]

# --- Generar mensaje con IA desde Hugging Face ---
def ai_generate_message(reminders):
    prompt = f"Reformula esta lista de tareas diarias de manera clara y motivante en español: {reminders}"
    response = requests.post(
        "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct",
        headers={"Authorization": f"Bearer {HF_TOKEN}"},
        json={"inputs": prompt},
    )
    result = response.json()
    return result[0]["generated_text"] if isinstance(result, list) else str(result)

# --- Enviar recordatorio a Telegram ---
def send_reminder():
    today = datetime.now().strftime("%d-%m-%Y")
    message = ai_generate_message(reminders)
    final_message = f"📅 Recordatorios del día ({today}):\n\n{message}"
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=final_message)

if __name__ == "__main__":
    send_reminder()
