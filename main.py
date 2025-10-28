# =========================================================
# 🧠 PROYECTO: Generador de desafíos diarios con IA (Groq API)
# Autor: Francisco Lodi
# =========================================================
# ✨ Características:
# - Diseño modular, limpio y robusto
# - Historial JSON con escritura atómica y backup automático
# - Parser JSON tolerante
# - Envío a Telegram con logs claros
# =========================================================

from datetime import datetime
from pathlib import Path
from telegram import Bot
from groq import Groq
import os, json, re, time, tempfile, shutil, sys

# =========================================================
# ⚙️ CONFIGURACIÓN GLOBAL
# =========================================================

CONFIG = {
    "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
    "TELEGRAM_TOKEN": os.getenv("TELEGRAM_TOKEN"),
    "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID"),
    "HIST_PATH": Path(os.getenv("HIST_PATH", "historial_desafios.json")),
    "MAX_DIAS_HIST": int(os.getenv("MAX_DIAS_HIST", "30")),
    "MAX_REINTENTOS": int(os.getenv("MAX_REINTENTOS", "5")),
    "PAUSA_SEG": float(os.getenv("PAUSA_SEG", "2")),
    "DRY_RUN": os.getenv("DRY_RUN", "0") == "1",
}

# Inicializar clientes solo si no es modo prueba
GROQ = Groq(api_key=CONFIG["GROQ_API_KEY"]) if not CONFIG["DRY_RUN"] else None
BOT = Bot(token=CONFIG["TELEGRAM_TOKEN"]) if not CONFIG["DRY_RUN"] else None


# =========================================================
# 📘 UTILIDADES DE ARCHIVO
# =========================================================

def leer_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        backup = path.with_suffix(f".bak_{datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(path, backup)
        print(f"⚠️ JSON corrupto, backup en {backup}")
        return {}
    except Exception as e:
        print(f"⚠️ Error leyendo {path.name}: {e}")
        return {}

def escribir_json_atomico(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp.flush(); os.fsync(tmp.fileno())
        temp_name = tmp.name
    os.replace(temp_name, path)

def guardar_historial(fecha: str, desafios: dict):
    path = CONFIG["HIST_PATH"]
    hist = leer_json(path)
    hist[fecha] = desafios
    fechas = sorted(hist.keys())[-CONFIG["MAX_DIAS_HIST"]:]
    hist = {k: hist[k] for k in fechas}
    escribir_json_atomico(path, hist)
    print(f"📝 Historial actualizado ({len(hist)} días) → {path.resolve()}")


# =========================================================
# 🧠 LÓGICA DE DESAFÍOS
# =========================================================

def extraer_json_robusto(texto: str):
    if not texto:
        return None
    for attempt in range(2):
        try:
            return json.loads(texto)
        except:
            texto = re.sub(r"'", '"', texto)
            texto = re.sub(r'\\(?![\\/"bfnrt])', r'\\\\', texto)
            match = re.search(r"\{.*\}", texto, re.DOTALL)
            texto = match.group(0) if match else texto
    return None

def generar_desafios(recientes: dict) -> dict:
    if CONFIG["DRY_RUN"]:
        print("🧪 Modo prueba (DRY_RUN=1)")
        return {
            "CrossFit": "5 series de 10 burpees.",
            "Alimentación": "Incluye 2 frutas frescas hoy.",
            "Bienestar": "Medita 10 minutos antes de dormir."
        }

    prompt = (
        "Genera tres desafíos diarios distintos en español: CrossFit, Alimentación y Bienestar. "
        f"Evita repetir: {recientes}. Devuelve solo JSON con "
        '{"CrossFit": "texto", "Alimentación": "texto", "Bienestar": "texto"}.'
    )

    for intento in range(1, CONFIG["MAX_REINTENTOS"] + 1):
        try:
            resp = GROQ.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "Devuelve solo JSON válido."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=300,
            )
            texto = resp.choices[0].message.content.strip()
            data = extraer_json_robusto(texto)
            if data and all(k in data for k in ("CrossFit", "Alimentación", "Bienestar")):
                return data
        except Exception as e:
            print(f"⚠️ Intento {intento} falló: {e}")
    return {"Error": "No se pudo generar desafíos válidos."}


# =========================================================
# 📬 ENVÍO A TELEGRAM
# =========================================================

def enviar_telegram(msg: str):
    t = datetime.now().strftime('%H:%M:%S')
    texto = f"⏰ {t}\n{msg}"
    if CONFIG["DRY_RUN"]:
        print(f"[Simulado] {texto}")
    else:
        BOT.send_message(chat_id=CONFIG["TELEGRAM_CHAT_ID"], text=texto)
    print(texto)


# =========================================================
# 🚀 CICLO PRINCIPAL
# =========================================================

def ejecutar():
    fecha = datetime.now().strftime("%Y-%m-%d")
    print(f"\n🧠 Iniciando ciclo de desafíos — {fecha}\n")

    recientes = leer_json(CONFIG["HIST_PATH"])
    recientes = {k: set(v.values()) if isinstance(v, dict) else set() for k, v in recientes.items()}
    desafios = generar_desafios(recientes)

    if "Error" in desafios:
        enviar_telegram(f"⚠️ Error: {desafios['Error']}")
        guardar_historial(fecha, desafios)
        return

    enviar_telegram(f"🧭 Desafíos del día — {fecha}")
    for cat, texto in desafios.items():
        enviar_telegram(f"📘 {cat}:\n{texto}")
        time.sleep(CONFIG["PAUSA_SEG"])

    guardar_historial(fecha, desafios)
    print("✅ Proceso completado correctamente.\n")


# =========================================================
# 🏁 EJECUCIÓN
# =========================================================

if __name__ == "__main__":
    try:
        ejecutar()
    except Exception as e:
        print(f"💥 Error crítico: {e}")
        guardar_historial(datetime.now().strftime("%Y-%m-%d"), {"Error": str(e)})
        sys.exit(1)
