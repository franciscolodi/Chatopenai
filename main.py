# =========================================================
# 🧠 PROYECTO: Generador de desafíos diarios con IA (Groq API)
# =========================================================

from groq import Groq
from telegram import Bot
from datetime import datetime
import os
import time
import json
import random

# --- Configuración ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HIST_PATH = "historial_desafios.json"

# --- Inicializar clientes ---
client = Groq(api_key=GROQ_API_KEY)
bot = Bot(token=TELEGRAM_TOKEN)

# =========================================================
# 🧩 UTILIDADES DE HISTORIAL
# =========================================================

def cargar_historial():
    if os.path.exists(HIST_PATH):
        with open(HIST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def guardar_historial(fecha, desafios):
    historial = cargar_historial()
    historial[fecha] = desafios
    # Mantener solo últimos 30 días
    fechas = sorted(historial.keys())[-30:]
    historial = {k: historial[k] for k in fechas}
    os.makedirs(os.path.dirname(HIST_PATH), exist_ok=True)
    with open(HIST_PATH, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=2)

def obtener_desafios_recientes(dias=5):
    historial = cargar_historial()
    ultimos = [v for k, v in sorted(historial.items())[-dias:]]
    # Flatten para extraer solo los textos de cada categoría
    recientes = {"CrossFit": set(), "Alimentación": set(), "Bienestar": set()}
    for dia in ultimos:
        for cat in recientes:
            if cat in dia:
                recientes[cat].add(dia[cat])
    return recientes

# =========================================================
# 🧠 GENERADOR DE DESAFÍOS (IA)
# =========================================================

def generar_desafios_diarios():
    recientes = obtener_desafios_recientes()
    prompt = (
        f"Genera tres desafíos diarios distintos y concisos en español, uno por categoría: "
        f"CrossFit, Alimentación y Bienestar. Evita repetir estos desafíos recientes: {recientes}. "
        "Cada desafío debe ser una frase breve, clara, científica y pragmática. "
        "Devuelve **solo** un objeto JSON válido, sin texto adicional, sin Markdown. "
        "Cada valor debe ser una frase breve."
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Eres un especialista en rendimiento humano, nutrición y fisiología. Devuelve JSON limpio."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=250,
        )

        contenido = response.choices[0].message.content.strip()
        contenido = contenido.replace("```json", "").replace("```", "").strip()
        desafios = json.loads(contenido)

        # Validar que no repita desafíos recientes (backup)
        for cat in desafios:
            if desafios[cat] in recientes.get(cat, set()):
                # Añadir un pequeño modificador para variar
                desafios[cat] = f"{desafios[cat]} (variante)"
        return desafios

    except json.JSONDecodeError:
        return {"Error": "Respuesta no es JSON válido", "Contenido": contenido}
    except Exception as e:
        return {"Error": str(e)}

# =========================================================
# 🚀 ENVÍO DE DESAFÍOS A TELEGRAM
# =========================================================

def enviar_a_telegram(mensaje):
    timestamp = datetime.now().strftime('%H:%M:%S')
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"⏰ {timestamp}\n{mensaje}")
    print(f"[{timestamp}] {mensaje}")

def ejecutar_ciclo_desafios():
    desafios = generar_desafios_diarios()
    fecha = datetime.now().strftime("%Y-%m-%d")

    if "Error" in desafios:
        enviar_a_telegram(f"⚠️ Error generando desafíos: {desafios['Error']}")
        guardar_historial(fecha, {"Error": desafios["Error"]})
        return

    header = f"🧭 Desafíos del día — {fecha}"
    enviar_a_telegram(header)

    for categoria, texto in desafios.items():
        mensaje = f"📘 {categoria}:\n{texto}"
        enviar_a_telegram(mensaje)
        time.sleep(3)  # pausa entre mensajes

    # Guardar historial
    guardar_historial(fecha, desafios)

# =========================================================
# 🏁 EJECUCIÓN PRINCIPAL
# =========================================================

if __name__ == "__main__":
    print("🧠 Iniciando ciclo de desafíos diarios...")
    ejecutar_ciclo_desafios()
    print("✅ Envío completado.")
