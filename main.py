import os
from openai import OpenAI
from datetime import datetime
from telegram import Bot
from dotenv import load_dotenv

# --- Cargar variables desde .env ---
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=TELEGRAM_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

# --- Lista de recordatorios importantes ---
reminders = [
    "Revisar informe semanal de producción",
    "Verificar stock de materia prima",
    "Enviar reporte de mantenimiento",
    "Preparar reunión del lunes con jefatura",
]

# --- Generar mensaje con IA ---
def ai_generate_message(reminders):
    prompt = f"""
    Actúa como un asistente inteligente que envía recordatorios diarios.
    Reformula y prioriza esta lista de recordatorios para hacerla más clara y motivante:
    {reminders}
    """

    ###

    response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content

# --- Enviar recordatorio ---
def send_reminder():
    today = datetime.now().strftime("%d-%m-%Y")
    message = ai_generate_message(reminders)
    final_message = f"📅 Recordatorios del día ({today}):\n\n{message}"
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=final_message)

if __name__ == "__main__":
    send_reminder()

