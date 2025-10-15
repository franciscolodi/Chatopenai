# =========================================================
# 🧬 DESAFÍOS INTELIGENTES IA — (vanguardista, modular, científico)
# =========================================================

from groq import Groq
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
from typing import Dict, Any
import os, json, asyncio

# --- Configuración ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HIST_PATH = "data/historial.json"

client = Groq(api_key=GROQ_API_KEY)
bot = Bot(token=TELEGRAM_TOKEN)

# =========================================================
# 🧩 UTILIDADES
# =========================================================

def load_history() -> Dict[str, Any]:
    if os.path.exists(HIST_PATH):
        with open(HIST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_history(date: str, data: Dict[str, Any]):
    hist = load_history()
    hist[date] = data
    hist = dict(sorted(hist.items())[-30:])  # mantener 30 días
    os.makedirs(os.path.dirname(HIST_PATH), exist_ok=True)
    with open(HIST_PATH, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)

# =========================================================
# 🧠 GENERADOR DE DESAFÍOS (IA)
# =========================================================

async def generar_desafios() -> Dict[str, str]:
    recientes = [v for _, v in sorted(load_history().items())[-5:]]
    prompt = f"""
    Genera tres desafíos distintos y precisos para hoy en español:
    - Uno de CrossFit (rendimiento físico).
    - Uno de Alimentación (nutrición aplicada).
    - Uno de Bienestar (neurociencia, descanso o hábitos).
    Evita repetir los siguientes desafíos recientes: {recientes}.
    Estilo: sobrio, científico, directo.
    Devuelve SOLO un JSON válido con claves: CrossFit, Alimentación, Bienestar.
    """
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Eres un experto en rendimiento humano, nutrición y bienestar. Devuelve JSON limpio."},
                {"role": "user", "content": prompt.strip()},
            ],
            temperature=0.45,
            max_tokens=250,
        )
        data = response.choices[0].message.content.strip()
        data = data.replace("```json", "").replace("```", "").strip()
        return json.loads(data)
    except Exception as e:
        return {"Error": str(e)}

# =========================================================
# 🚀 ENVÍO DE DESAFÍOS A TELEGRAM
# =========================================================

async def enviar_desafios(update: Update = None, context: ContextTypes.DEFAULT_TYPE = None):
    date = datetime.now().strftime("%Y-%m-%d")
    desafios = await generar_desafios()

    if "Error" in desafios:
        msg = f"⚠️ Error al generar desafíos: {desafios['Error']}"
        if update: await update.message.reply_text(msg)
        else: await bot.send_message(chat_id=CHAT_ID, text=msg)
        return

    save_history(date, desafios)

    header = f"🧭 Desafíos del día — {date}\n────────────────────────"
    await bot.send_message(chat_id=CHAT_ID, text=header)

    for cat, text in desafios.items():
        mensaje = f"📘 *{cat}*\n{text}\n\nResponde con ✅ hecho o ❌ omitido."
        await bot.send_message(chat_id=CHAT_ID, text=mensaje, parse_mode="Markdown")
        await asyncio.sleep(2)

# =========================================================
# 🗂️ REGISTRO DE RESPUESTAS
# =========================================================

async def registrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    usuario = update.message.from_user.username or update.message.from_user.first_name
    fecha = datetime.now().strftime("%Y-%m-%d")
    hist = load_history()

    if fecha not in hist:
        await update.message.reply_text("⚠️ No hay desafíos para hoy.")
        return

    for cat in hist[fecha]:
        if isinstance(hist[fecha][cat], dict) and "respuestas" in hist[fecha][cat]:
            hist[fecha][cat]["respuestas"][usuario] = text
        else:
            hist[fecha][cat] = {"texto": hist[fecha][cat], "respuestas": {usuario: text}}

    save_history(fecha, hist[fecha])
    await update.message.reply_text(f"Registro actualizado: {text}")

# =========================================================
# 🧩 MAIN BOT
# =========================================================

async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("desafios", enviar_desafios))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, registrar))

    print("🤖 Bot IA en marcha — modo científico vanguardista")
    await app.run_polling()

if __name__ == "__main__":
    from telegram.ext import ApplicationBuilder

    # Construye la app
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("desafios", enviar_desafios))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, registrar))

    print("🤖 Bot IA en marcha — modo científico vanguardista")
    
    # Ejecuta polling de manera segura, sin asyncio.run ni loop.run_forever
    app.run_polling()
