import os
import time
from datetime import datetime
from telegram import Bot
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

# --- Cargar variables ---
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HF_TOKEN = os.getenv("HF_TOKEN")

# --- Inicializar bot de Telegram ---
bot = Bot(token=TELEGRAM_TOKEN)

# --- Inicializar cliente Hugging Face ---
client = InferenceClient(api_key=HF_TOKEN)

# --- Lista de frases o tareas a motivar ---
tareas = [
    "Revisar informe",
    "Enviar reporte",
    "Organizar reuniones",
    "Responder correos pendientes"
]

# --- Función para generar frase motivacional ---
def generar_frase_motivacional(tarea):
    prompt = (
        f"Convierte la siguiente tarea en una frase motivadora y positiva para alguien "
        f"que la debe realizar hoy: '{tarea}'. "
        "Escribe en español, con tono natural, inspirador y claro."
    )
    
    response = client.chat_completion(
        model="mistralai/Mistral-7B-Instruct-v0.2",
        messages=[
            {"role": "system", "content": "Eres un asistente experto en productividad y motivación."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=100,
        temperature=0.8
    )
    
    return response.choices[0].message["content"]

# --- Enviar frases a Telegram ---
for tarea in tareas:
    frase = generar_frase_motivacional(tarea)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {frase}")
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=frase)
    time.sleep(2)  # Pequeña pausa entre mensajes
