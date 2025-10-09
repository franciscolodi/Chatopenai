# --- Inicializar cliente Hugging Face ---
from huggingface_hub import InferenceClient
from datetime import datetime
import time
from telegram import Bot
import os

HF_TOKEN = os.getenv("HF_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

client = InferenceClient(api_key=HF_TOKEN)
bot = Bot(token=TELEGRAM_TOKEN)

# --- Lista de categorías de desafíos ---
desafios = [
    "CrossFit: haz un circuito de 20 minutos con burpees, sentadillas y push-ups",
    "Alimentación: prepara una comida saludable rica en proteínas y vegetales",
    "Salud y bienestar: medita 10 minutos y bebe 2 litros de agua",
    "CrossFit: realiza 50 saltos con cuerda y 30 lunges alternados",
    "Alimentación: evita azúcares refinados hoy y come frutas naturales",
    "Salud y bienestar: haz una caminata de 30 minutos al aire libre"
]

# --- Función para generar desafío motivador ---
def generar_desafio_motivador(desafio):
    prompt = (
        f"Convierte el siguiente desafío diario en una frase motivadora, concisa y clara "
        f"para alguien que quiere mejorar su salud, alimentación y entrenamiento: '{desafio}'. "
        "Escribe en español, con tono inspirador y enérgico."
    )
    
    response = client.chat_completion(
        model="mistralai/Mistral-7B-Instruct-v0.2",
        messages=[
            {"role": "system", "content": "Eres un asistente experto en motivación, fitness y bienestar."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=100,
        temperature=0.8
    )
    
    return response.choices[0].message["content"]

# --- Enviar desafíos a Telegram ---
for desafio in desafios:
    frase = generar_desafio_motivador(desafio)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {frase}")
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=frase)
    time.sleep(2)  # Pequeña pausa entre mensajes

