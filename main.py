from groq import Groq
from telegram import Bot
from datetime import datetime
from pathlib import Path
import os, json, re, time, tempfile, sys

# =========================================================
# ⚙️ CONFIGURACIÓN
# =========================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HIST_PATH = Path(os.getenv("HIST_PATH", "historial_desafios.json"))
DRY_RUN = os.getenv("DRY_RUN", "0") == "1"

MAX_REINTENTOS = 5
MAX_DIAS_HIST = 30

# Inicializar clientes (solo si no es modo prueba)
client = Groq(api_key=GROQ_API_KEY) if not DRY_RUN else None
bot = Bot(token=TELEGRAM_TOKEN) if not DRY_RUN else None


# =========================================================
# 📘 HISTORIAL ROBUSTO
# =========================================================

def leer_historial() -> dict:
    """Lee el JSON, o crea uno vacío si no existe o está corrupto."""
    if not HIST_PATH.exists():
        print(f"ℹ️ Creando nuevo historial en {HIST_PATH.resolve()}")
        return {}
    try:
        with open(HIST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        print("⚠️ Historial corrupto, reiniciado.")
        return {}

def guardar_historial(fecha: str, desafios: dict):
    """Guarda o crea historial en JSON (escritura segura)."""
    hist = leer_historial()
    hist[fecha] = desafios
    # Mantiene solo los últimos N días
    fechas = sorted(hist.keys())[-MAX_DIAS_HIST:]
    hist = {k: hist[k] for k in fechas}

    HIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = HIST_PATH.with_suffix(".tmp")

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)
    os.replace(tmp, HIST_PATH)
    print(f"✅ Historial guardado → {HIST_PATH.resolve()}")


# =========================================================
# 🧠 IA Y PARSER
# =========================================================

def extraer_json_robusto(texto: str):
    """Intenta recuperar un JSON incluso si viene con comillas o texto extra."""
    try:
        return json.loads(texto)
    except:
        texto = re.sub(r"'", '"', texto)
        match = re.search(r"\{.*\}", texto, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass
    return None

def generar_desafios() -> dict:
    """Genera o simula desafíos diarios."""
    if DRY_RUN:
        print("🧪 Modo prueba (sin IA ni Telegram)")
        return {
            "CrossFit": "5 series de 10 burpees.",
            "Alimentación": "Consume dos frutas frescas hoy.",
            "Bienestar": "Realiza 10 minutos de respiración profunda."
        }

    prompt = (
        "Genera tres desafíos diarios distintos: CrossFit, Alimentación y Bienestar. "
        "Devuelve solo JSON con formato "
        '{"CrossFit": "texto", "Alimentación": "texto", "Bienestar": "texto"}.'
    )

    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            resp = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "Devuelve solo JSON válido."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=300,
            )
            txt = resp.choices[0].message.content.strip()
            data = extraer_json_robusto(txt)
            if isinstance(data, dict):
                return data
        except Exception as e:
            print(f"⚠️ Intento {intento} falló: {e}")
    return {"Error": "No se pudo generar desafíos válidos."}


# =========================================================
# 📬 TELEGRAM
# =========================================================

def enviar(msg: str):
    """Envía mensaje o lo imprime si es DRY_RUN."""
    timestamp = datetime.now().strftime('%H:%M:%S')
    texto = f"⏰ {timestamp}\n{msg}"
    if DRY_RUN:
        print(f"[Simulado] {texto}")
    else:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=texto)
    print(texto)


# =========================================================
# 🚀 PROCESO PRINCIPAL
# =========================================================

def main():
    fecha = datetime.now().strftime("%Y-%m-%d")
    print(f"\n🧠 Iniciando ciclo {fecha}")

    desafios = generar_desafios()
    if "Error" in desafios:
        enviar(f"⚠️ {desafios['Error']}")
    else:
        enviar(f"🧭 Desafíos del día — {fecha}")
        for cat, texto in desafios.items():
            enviar(f"📘 {cat}: {texto}")
            time.sleep(2)

    guardar_historial(fecha, desafios)
    print("✅ Ejecución completada.\n")


# =========================================================
# 🏁 EJECUCIÓN
# =========================================================

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"💥 Error inesperado: {e}")
        fecha = datetime.now().strftime("%Y-%m-%d")
        guardar_historial(fecha, {"Error": str(e)})
        sys.exit(1)
