from groq import Groq
from telegram import Bot
from telegram import ParseMode
from datetime import datetime
from pathlib import Path
import os, json, re, time, sys, tempfile, shutil, traceback

# =========================================================
# ⚙️ CONFIGURACIÓN
# =========================================================
GROQ_API_KEY   = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Carpeta de estado persistente (puedes cambiarla a "data" si prefieres en repo)
STATE_DIR = Path(os.getenv("STATE_DIR", "./state")).resolve()
STATE_DIR.mkdir(parents=True, exist_ok=True)

HIST_PATH = Path(os.getenv("HIST_PATH", STATE_DIR / "historial_desafios.json")).resolve()

DRY_RUN = os.getenv("DRY_RUN", "0") == "1"
MAX_REINTENTOS = 5
MAX_DIAS_HIST = 30

client = Groq(api_key=GROQ_API_KEY) if not DRY_RUN else None
bot    = Bot(token=TELEGRAM_TOKEN) if not DRY_RUN else None


# =========================================================
# 🪵 LOGGING
# =========================================================
def log(msg: str, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")


# =========================================================
# 🔐 UTILIDADES HISTORIAL
# =========================================================
def _write_atomic_json(target: Path, data: dict):
    """Escritura atómica con tmp y respaldo .bak."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(target.parent), prefix=target.stem, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        # Backup previo si existe
        if target.exists():
            bak = target.with_suffix(target.suffix + ".bak")
            shutil.copy2(target, bak)
        os.replace(tmp_path, target)
    except Exception:
        # Limpieza de tmp si algo falla
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        raise


def leer_historial() -> dict:
    """Lee JSON de historial; si no existe o está corrupto, devuelve {}."""
    if not HIST_PATH.exists() or HIST_PATH.stat().st_size == 0:
        log(f"No hay historial, se creará al guardar en: {HIST_PATH}", "INFO")
        return {}
    try:
        with open(HIST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        log("Historial corrupto — se reinicia (se conserva .bak).", "WARN")
        # Mueve el corrupto a .bak_corrupt con timestamp
        corrupt_bak = HIST_PATH.with_suffix(HIST_PATH.suffix + f".corrupt-{int(time.time())}.bak")
        try:
            shutil.move(str(HIST_PATH), str(corrupt_bak))
        except Exception:
            pass
        return {}
    except Exception as e:
        log(f"Error leyendo historial: {e}", "ERROR")
        return {}


def guardar_historial(fecha: str, desafios: dict):
    """Guarda/rota historial manteniendo MAX_DIAS_HIST días."""
    try:
        hist = leer_historial()
        hist[fecha] = desafios
        # Rotación por fecha (clave YYYY-MM-DD)
        fechas = sorted(hist.keys())[-MAX_DIAS_HIST:]
        hist = {k: hist[k] for k in fechas}
        _write_atomic_json(HIST_PATH, hist)
        log(f"✅ Historial actualizado: {HIST_PATH}")
    except Exception as e:
        traceback.print_exc()
        log(f"💥 Error guardando historial: {e}", "ERROR")


# =========================================================
# 🧠 IA Y PARSER
# =========================================================
EXPECTED_KEYS = {"CrossFit", "Alimentación", "Bienestar", "WOD"}


def _maybe_coerce_to_expected(d: dict) -> dict:
    """Normaliza claves esperadas si vienen con mayúsculas/minúsculas u otros espacios."""
    out = {}
    mapping = {k.lower(): k for k in EXPECTED_KEYS}
    for k, v in d.items():
        key_norm = mapping.get(str(k).strip().lower())
        if key_norm:
            out[key_norm] = v if isinstance(v, str) else str(v)
    return out

def extraer_json_robusto(texto: str):
    """Intenta recuperar JSON válido desde un texto potencialmente mezclado."""
    if not texto:
        return None
    # 1) Intento directo
    try:
        data = json.loads(texto)
        if isinstance(data, dict):
            return _maybe_coerce_to_expected(data) or data
        return data
    except Exception:
        pass
    # 2) Reemplazo de comillas simples -> dobles y extracción del primer {...}
    try:
        safe = re.sub(r"'", '"', texto)
        m = re.search(r"\{.*?\}", safe, re.DOTALL)
        if m:
            data = json.loads(m.group(0))
            if isinstance(data, dict):
                return _maybe_coerce_to_expected(data) or data
            return data
    except Exception:
        pass
    return None


def generar_desafios() -> dict:
    """Genera desafíos variados con IA Groq basándose en historial previo, temas rotativos y un WOD."""
    import random

    if DRY_RUN:
        log("🧪 Modo prueba activo — generación simulada.")
        return {
            "CrossFit": "Haz un EMOM de 10 minutos alternando 12 burpees y 15 air squats.",
            "Alimentación": "Incluye una ensalada con hojas verdes y proteínas en tu almuerzo.",
            "Bienestar": "Dedica 10 minutos a estirarte escuchando música relajante.",
            "WOD": "Completa un AMRAP de 20 minutos con 15 kettlebell swings, 10 push-ups y 200m de carrera."
        }

    # === Obtener historial reciente ===
    hist = leer_historial()
    ultimos = list(hist.values())[-3:]  # últimos 3 días
    texto_hist = "\n".join([
        f"Día {i+1}: {json.dumps(d, ensure_ascii=False)}" for i, d in enumerate(ultimos)
    ]) if ultimos else "Sin registros previos."

    # === Temas rotativos ===
    temas_cf = ["fuerza", "resistencia", "cardio", "movilidad", "core", "agilidad"]
    temas_food = ["vegetales", "hidratación", "proteínas", "legumbres", "fibra", "balance"]
    temas_well = ["mindfulness", "descanso", "gratitud", "contacto social", "naturaleza", "autoestima"]
    tipos_wod = ["EMOM", "AMRAP", "For Time"]

    tema_actual = {
        "CrossFit": random.choice(temas_cf),
        "Alimentación": random.choice(temas_food),
        "Bienestar": random.choice(temas_well),
        "WOD": random.choice(tipos_wod)
    }

    random_seed = random.randint(1000, 9999)

    # === Prompt avanzado ===
    prompt = f"""
Eres un coach experto en CrossFit, nutrición y bienestar con creatividad diaria.

A continuación se muestran los desafíos recientes:
{texto_hist}

Crea NUEVOS desafíos diferentes para hoy, evitando repetir ejercicios, comidas o rutinas similares.
Hoy enfócate en los siguientes temas:
- CrossFit: {tema_actual['CrossFit']}
- Alimentación: {tema_actual['Alimentación']}
- Bienestar: {tema_actual['Bienestar']}
- WOD del día: {tema_actual['WOD']} (duración mínima 20 minutos)

📋 Reglas para el WOD:
- Si el tipo es EMOM: define un esquema claro (por ejemplo, “20 min EMOM: min 1 burpees, min 2 kettlebell swings…”).
- Si el tipo es AMRAP: define un set de ejercicios variados para repetir durante 20 minutos o más.
- Si es For Time: especifica un número total de rondas o repeticiones y un objetivo temporal (mínimo 20 minutos de trabajo).
- Incluye movimientos funcionales variados (cardio, fuerza, core, gimnásticos).
- Usa lenguaje motivacional, como lo haría un coach de box.
- No incluyas explicaciones, solo texto conciso del desafío.

Devuelve SOLO un JSON válido con este formato:
{{
  "CrossFit": "texto",
  "Alimentación": "texto",
  "Bienestar": "texto",
  "WOD": "texto"
}}

Semilla creativa aleatoria: {random_seed}
"""

    # === Llamada al modelo ===
    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            resp = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "Eres un generador de desafíos CrossFit y bienestar. Responde solo con JSON válido."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=400,
            )

            content = resp.choices[0].message.content.strip()
            data = extraer_json_robusto(content)

            if isinstance(data, dict) and all(k in data for k in ["CrossFit", "Alimentación", "Bienestar", "WOD"]):
                log(f"🎯 Desafíos generados exitosamente (semilla {random_seed})")
                return data

            log(f"Intento {intento}: respuesta no válida, reintento...", "WARN")
        except Exception as e:
            log(f"Intento {intento} falló: {e}", "WARN")

        time.sleep(min(intento, 3))  # backoff progresivo

    return {"Error": "No se pudieron generar desafíos válidos tras varios intentos."}




# =========================================================
# 🧹 ESCAPE MARKDOWN V2 (Telegram)
# =========================================================
_MD2_ESCAPE_RE = re.compile(r'([_*\[\]()~`>#+\-=|{}.!\\])')

def md2_escape(text: str) -> str:
    return _MD2_ESCAPE_RE.sub(r'\\\1', text)


# =========================================================
# 📬 TELEGRAM
# =========================================================
def enviar_desafios(fecha: str, desafios: dict):
    """Envía mensaje a Telegram (o simula) con los desafíos diarios, incluyendo el WOD."""
    if not isinstance(desafios, dict):
        desafios = {"Error": "Formato inesperado"}

    # --- Modo error ---
    if "Error" in desafios:
        titulo = md2_escape(f"⚠️ Error ({fecha})")
        cuerpo = md2_escape(str(desafios["Error"]))
        msg = f"*{titulo}*\n\n{cuerpo}"
    else:
        # --- Título dinámico según el tipo de WOD ---
        tema_dia = ""
        if "WOD" in desafios:
            wod_text = desafios["WOD"].lower()
            if "amrap" in wod_text:
                tema_dia = "🔥 Día de resistencia"
            elif "emom" in wod_text:
                tema_dia = "⚡ Día de constancia"
            elif "for time" in wod_text:
                tema_dia = "🏁 Día de intensidad"
            else:
                tema_dia = "💪 Día de energía"
        else:
            tema_dia = "🧭 Desafíos del día"

        titulo = md2_escape(f"{tema_dia} ({fecha})")

        # --- Cuerpo del mensaje ---
        lineas = []
        for k in ["CrossFit", "Alimentación", "Bienestar", "WOD"]:
            if k in desafios:
                lineas.append(f"• *{md2_escape(k)}*: {md2_escape(str(desafios[k]))}")

        cuerpo = "\n".join(lineas) if lineas else md2_escape(json.dumps(desafios, ensure_ascii=False))
        msg = f"*{titulo}*\n\n{cuerpo}"

    # --- Modo simulación ---
    if DRY_RUN:
        print(f"[Simulado Telegram] {msg}")
        return

    # --- Envío real ---
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=msg,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        log("📩 Desafíos enviados correctamente a Telegram.")
    except Exception as e:
        log(f"Telegram error: {e}", "ERROR")



# =========================================================
# 🚀 PROCESO PRINCIPAL
# =========================================================
def run_cycle():
    fecha = datetime.now().strftime("%Y-%m-%d")
    log(f"Iniciando ciclo — fecha: {fecha} | HIST_PATH: {HIST_PATH}")

    desafios = generar_desafios()
    # Enviar sin bloquear historial
    enviar_desafios(fecha, desafios)
    # Guardar SIEMPRE
    guardar_historial(fecha, desafios)
    log("Ciclo completado ✅")


# =========================================================
# 🏁 MAIN
# =========================================================
if __name__ == "__main__":
    try:
        run_cycle()
    except Exception as e:
        log(f"💥 Error fatal: {e}", "ERROR")
        traceback.print_exc()
        # Aún así, tratamos de registrar el error del día
        try:
            fecha = datetime.now().strftime("%Y-%m-%d")
            guardar_historial(fecha, {"Error": str(e)})
        except Exception:
            pass
        sys.exit(1)




