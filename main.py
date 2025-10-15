# =========================================================
# 🧠 PROYECTO: Generador de desafíos diarios con IA (Groq API)
# =========================================================

from groq import Groq
from telegram import Bot
from datetime import datetime
import os
import time
import json
import re

# --- Configuración ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HIST_PATH = "historial_desafios.json"
MAX_REINTENTOS = 3

# --- Inicializar clientes ---
client = Groq(api_key=GROQ_API_KEY)
bot = Bot(token=TELEGRAM_TOKEN)

# =========================================================
# 🧩 UTILIDADES DE HISTORIAL
# =========================================================

def cargar_historial():
    if os.path.exists(HIST_PATH):
        try:
            with open(HIST_PATH, "r", encoding="utf-8") as f:
                contenido = f.read().strip()
                if not contenido:
                    return {}
                return json.loads(contenido)
        except json.JSONDecodeError:
            print(f"⚠️ Historial corrupto o inválido, se reinicia: {HIST_PATH}")
            return {}
    return {}

def guardar_historial(fecha, desafios):
    historial = cargar_historial()
    historial[fecha] = desafios
    fechas = sorted(historial.keys())[-30:]
    historial = {k: historial[k] for k in fechas}

    folder = os.path.dirname(HIST_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)

    with open(HIST_PATH, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=2)

def obtener_desafios_recientes(dias=5):
    historial = cargar_historial()
    ultimos = [v for k, v in sorted(historial.items())[-dias:]]
    recientes = {"CrossFit": set(), "Alimentación": set(), "Bienestar": set()}
    for dia in ultimos:
        for cat in recientes:
            if cat in dia:
                recientes[cat].add(str(dia[cat]))
    return recientes

# =========================================================
# 🧠 UTILIDAD PARA EXTRAER JSON
# =========================================================

def extraer_json(texto):
    try:
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        if match:
            return json.loads(match.group())
    except json.JSONDecodeError:
        return None
    return None

# =========================================================
# 🧠 GENERADOR DE DESAFÍOS (IA)
# =========================================================

def generar_desafio_por_categoria(prompt, recientes):
    """Genera un objeto JSON válido de desafíos, reintentando si es necesario"""
    for intento in range(1, MAX_REINTENTOS + 1):
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
            desafios = extraer_json(contenido)
            if not desafios:
                print(f"⚠️ Intento {intento}: No se detectó JSON válido")
                continue

            # Evitar repetir desafíos recientes
            for cat in ["CrossFit", "Alimentación", "Bienestar"]:
                if cat in desafios and str(desafios[cat]) in recientes.get(cat, set()):
                    print(f"⚠️ Desafío repetido en {cat}, se genera variante")
                    desafios[cat] = f"{desafios[cat]} (variante {intento})"

            return desafios

        except Exception as e:
            print(f"⚠️ Intento {intento}: Error generando desafío: {e}")

    # Si falla todos los intentos
    return {"Error": "No se pudo generar JSON válido tras varios intentos"}

def generar_desafios_diarios():
    recientes = obtener_desafios_recientes()
    prompt = (
        f"Genera tres desafíos diarios distintos y concisos en español, uno por categoría: "
        f"CrossFit, Alimentación y Bienestar. Evita repetir estos desafíos recientes: {recientes}. "
        "Cada desafío debe ser una frase breve, clara, científica y pragmática. "
        "Devuelve solo un objeto JSON válido, sin texto adicional."
    )
    return generar_desafio_por_categoria(prompt, recientes)

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

    for categoria, contenido in desafios.items():
    # Si el contenido es un dict con clave 'desafío', extraemos el texto
    if isinstance(contenido, dict) and 'desafío' in contenido:
        texto = contenido['desafío']
    else:
        texto = str(contenido)  # fallback
    mensaje = f"📘 {categoria}:\n{texto}"
    enviar_a_telegram(mensaje)
    time.sleep(3)


    guardar_historial(fecha, desafios)

# =========================================================
# 🏁 EJECUCIÓN PRINCIPAL
# =========================================================

if __name__ == "__main__":
    print("🧠 Iniciando ciclo de desafíos diarios...")
    ejecutar_ciclo_desafios()
    print("✅ Envío completado.")

