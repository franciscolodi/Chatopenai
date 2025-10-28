from groq import Groq
from telegram import Bot
from datetime import datetime
from pathlib import Path
import os, json, re, time, sys

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

client = Groq(api_key=GROQ_API_KEY) if not DRY_RUN else None
bot = Bot(token=TELEGRAM_TOKEN) if not DRY_RUN else None


# =========================================================
# 🪵 LOGGING SIMPLE
# =========================================================
def log(msg: str, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")


# =========================================================
# 📘 HISTORIAL ROBUSTO
# =========================================================
def leer_historial() -> dict:
    if not HIST_PATH.exists() or HIST_PATH.stat().st_size == 0:
        log(f"Creando nuevo historial en {HIST_PATH.resolve()}")
        return {}

    try:
        with open(HIST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        log("Historial corrupto — se reinicia.", "WARN")
        return {}

def guardar_historial(fecha: str, desafios: dict):
    hist = leer_historial()
    hist[fecha] = desafios
    fechas = sorted(hist.keys())[-MAX_DIAS_HIST:]
    hist = {k: hist[k] for k in fechas}

    HIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = HIST_PATH.with_suffix(".tmp")

    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False, indent=2)
        os.replace(tmp, HIST_PATH)
        log(f"Historial actualizado: {HIST_PATH.resolve()}")
    except Exception as e:
        log(f"Error guardando historial: {e}", "ERROR")
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


# =========================================================
# 🧠 IA Y PARSER
# =========================================================
def extraer_json_robusto(texto: str):
    """Intenta recuperar JSON válido aunque venga mezclado."""
    if not texto:
        return None
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        texto = re.sub(r"'", '"', texto)
        match = re.search(r"\{.*\}", texto, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                # Limpieza básica
                return {k.strip(): v.strip() for k, v in data.items()}
            except Exception:
                pass
    return None


def generar_desafios() -> dict:
    """Genera desafíos con IA Groq o simula si está en modo prueba."""
    if DRY_RUN:
        log("🧪 Modo prueba activo — generación simulada.")
        return {
            "CrossFit": "Haz 4 rondas de 12 burpees y 12 push-ups.",
            "Alimentación": "Incluye 2 frutas y evita azúcar refinada.",
            "Bienestar": "Dedica 10 minutos a respirar profundo y estirarte."
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
            data = extraer_json_robusto(resp.choices[0].message.content.strip())
            if isinstance(data, dict):
                return data
        except Exception as e:
            log(f"Intento {intento} falló: {e}", "WARN")
            time.sleep(intento)  # backoff progresivo
    return {"Error": "No se pudo generar desafíos válidos."}


# =========================================================
# 📬 TELEGRAM
# =========================================================
def enviar(msg: str):
    ts = datetime.now().strftime('%H:%M:%S')
    if DRY_RUN:
        print(f"[Simulado {ts}] {msg}")
        return
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
    except Exception as e:
        log(f"Telegram error: {e}", "ERROR")


# =========================================================
# 🚀 PROCESO PRINCIPAL
# =========================================================
def run_cycle():
    fecha = datetime.now().strftime("%Y-%m-%d")
    log(f"Iniciando ciclo diario — {fecha}")

    desafios = generar_desafios()

    if "Error" in desafios:
        enviar(f"⚠️ {desafios['Error']}")
    else:
        compact = "\n".join([f"📘 {k}: {v}" for k, v in desafios.items()])
        enviar(f"🧭 *Desafíos del día ({fecha})*\n\n{compact}")

    guardar_historial(fecha, desafios)
    log("Ciclo completado ✅\n")


# =========================================================
# 🏁 MAIN
# =========================================================
if __name__ == "__main__":
    try:
        run_cycle()
    except Exception as e:
        log(f"💥 Error fatal: {e}", "ERROR")
        fecha = datetime.now().strftime("%Y-%m-%d")
        guardar_historial(fecha, {"Error": str(e)})
        sys.exit(1)
