# =========================================================
# 🧠 PROYECTO: Generador de desafíos diarios con IA (Groq API)
# =========================================================

from groq import Groq
from telegram import Bot
from datetime import datetime
from pathlib import Path
import os
import time
import json
import re
import tempfile
import shutil

# --- Configuración ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Puedes moverlo a una carpeta dedicada si corres en GitHub Actions:
# por ejemplo ".data/historial_desafios.json"
HIST_PATH = Path("historial_desafios.json")

MAX_REINTENTOS = 5  # aumentamos para más robustez
MAX_DIAS_HIST = 30  # mantener 30 días máximo

# --- Validaciones básicas de credenciales ---
if not GROQ_API_KEY:
    raise RuntimeError("❌ Falta GROQ_API_KEY en variables de entorno.")
if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise RuntimeError("❌ Falta TELEGRAM_TOKEN o TELEGRAM_CHAT_ID en variables de entorno.")

# --- Inicializar clientes ---
client = Groq(api_key=GROQ_API_KEY)
bot = Bot(token=TELEGRAM_TOKEN)

# =========================================================
# 🧩 UTILIDADES DE HISTORIAL (robustas y atómicas)
# =========================================================

def _escritura_atomica_json(path: Path, data: dict):
    """
    Escribe JSON de forma atómica:
    1) escribe en un archivo temporal
    2) hace replace al destino
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_name = tmp.name
    # Reemplazo atómico (en *nix siempre; en Windows también funciona con replace)
    os.replace(tmp_name, path)

def _backup_si_corrupto(path: Path):
    """
    Si el JSON existe pero es inválido, lo renombramos como .bak con timestamp
    para no perderlo y arrancar limpio.
    """
    if path.exists():
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        bak = path.with_suffix(path.suffix + f".{ts}.bak")
        try:
            shutil.copy2(path, bak)
            print(f"⚠️ Historial inválido. Copia de seguridad creada: {bak}")
        except Exception as e:
            print(f"⚠️ No se pudo crear backup del historial: {e}")

def cargar_historial() -> dict:
    """
    Carga un dict { 'YYYY-MM-DD': {...desafios...}, ... }
    Si el archivo no existe o está vacío, devuelve {}.
    Si está corrupto, hace backup y devuelve {}.
    """
    if not HIST_PATH.exists():
        return {}
    try:
        texto = HIST_PATH.read_text(encoding="utf-8").strip()
        if not texto:
            return {}
        data = json.loads(texto)
        if not isinstance(data, dict):
            # Si alguien guardó una lista u otro tipo, lo respaldamos y reiniciamos
            _backup_si_corrupto(HIST_PATH)
            return {}
        return data
    except json.JSONDecodeError:
        _backup_si_corrupto(HIST_PATH)
        return {}
    except Exception as e:
        print(f"⚠️ Error leyendo historial: {e}")
        return {}

def _ordenar_y_recortar(historial: dict, max_dias: int = MAX_DIAS_HIST) -> dict:
    """
    Mantiene solo las últimas 'max_dias' fechas (ordenadas ascendente por fecha)
    """
    # Las claves tienen formato YYYY-MM-DD → orden lexicográfico sirve
    fechas = sorted(k for k in historial.keys() if re.fullmatch(r"\d{4}-\d{2}-\d{2}", k))
    if len(fechas) > max_dias:
        fechas = fechas[-max_dias:]
    return {k: historial[k] for k in fechas}

def guardar_historial(fecha: str, desafios: dict):
    """
    Guarda (o reemplaza) la entrada de una 'fecha' con escritura atómica, y
    conserva solo MAX_DIAS_HIST días.
    """
    historial = cargar_historial()
    historial[fecha] = desafios
    historial = _ordenar_y_recortar(historial, MAX_DIAS_HIST)
    _escritura_atomica_json(HIST_PATH, historial)

def obtener_desafios_recientes(dias: int = 5) -> dict:
    """
    Devuelve sets con textos recientes por categoría para evitar repeticiones.
    Estructura: {"CrossFit": set(), "Alimentación": set(), "Bienestar": set()}
    Ignora fechas con estructura inesperada.
    """
    historial = cargar_historial()
    # ordenamos y quedamos con los últimos N
    ordenado = _ordenar_y_recortar(historial, max_dias=max(len(historial), dias))
    ultimos_items = list(ordenado.items())[-dias:]

    recientes = {"CrossFit": set(), "Alimentación": set(), "Bienestar": set()}
    for _, dia in ultimos_items:
        if not isinstance(dia, dict):
            continue
        for cat in recientes.keys():
            if cat in dia and isinstance(dia[cat], str):
                recientes[cat].add(dia[cat])
    return recientes

# =========================================================
# 🧠 UTILIDAD PARA EXTRAER JSON ROBUSTO
# =========================================================

def extraer_json_robusto(texto: str):
    """
    Intenta extraer el primer objeto JSON '{}' del texto.
    - Normaliza comillas simples → dobles cuando parece JSON malformado.
    - Elimina basura fuera del primer '{}' grande.
    """
    if not texto:
        return None

    # 1) Intento directo rápido (por si viene limpio)
    try:
        return json.loads(texto)
    except Exception:
        pass

    # 2) Normalizar comillas simples → dobles (cuidado básico)
    texto_corr = re.sub(r"'", '"', texto)

    # 3) Tomar el primer dict que parezca JSON con DOTALL
    m = re.search(r"\{.*\}", texto_corr, flags=re.DOTALL)
    if not m:
        return None

    candidato = m.group(0)

    # 4) Quitar secuencias de escape rotas tipo "\n" mal cerradas
    candidato = re.sub(r'\\(?![\\/"bfnrt])', r'\\\\', candidato)

    # 5) Reintento final
    try:
        return json.loads(candidato)
    except Exception:
        # Limpieza mínima extra: compactar espacios
        candidato2 = re.sub(r"\s+", " ", candidato)
        try:
            return json.loads(candidato2)
        except Exception:
            return None

# =========================================================
# 🧠 GENERADOR DE DESAFÍOS
# =========================================================

def generar_desafio_por_categoria(prompt: str, recientes: dict) -> dict:
    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system",
                     "content": (
                         "Eres un especialista en rendimiento humano, nutrición y fisiología. "
                         "Devuelve únicamente JSON válido con claves exactamente: "
                         '"CrossFit", "Alimentación", "Bienestar".'
                     )},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=300,
            )

            contenido = (response.choices[0].message.content or "").strip()
            desafios = extraer_json_robusto(contenido)
            if not (isinstance(desafios, dict) and
                    all(k in desafios for k in ("CrossFit", "Alimentación", "Bienestar")) and
                    all(isinstance(desafios[k], str) for k in desafios)):
                print(f"⚠️ Intento {intento}: No se detectó JSON válido con estructura esperada")
                continue

            # Evitar repetir desafíos recientes
            for cat in ("CrossFit", "Alimentación", "Bienestar"):
                if desafios[cat] in recientes.get(cat, set()):
                    desafios[cat] = f"{desafios[cat]} (variante {intento})"

            return desafios

        except Exception as e:
            print(f"⚠️ Intento {intento}: Error generando desafío: {e}")

    return {"Error": "No se pudo generar JSON válido tras varios intentos"}

def generar_desafios_diarios() -> dict:
    recientes = obtener_desafios_recientes()
    prompt = (
        "Genera tres desafíos diarios distintos y concisos en español: "
        "CrossFit, Alimentación y Bienestar. "
        f"Evita repetir estos desafíos recientes (texto exacto): {recientes}. "
        "Cada desafío debe ser UNA sola frase breve, clara, basada en evidencia y pragmática. "
        "Devuelve únicamente un JSON con la estructura exacta: "
        '{"CrossFit": "texto", "Alimentación": "texto", "Bienestar": "texto"} '
        "Sin listas, sin comentarios, sin texto extra."
    )
    return generar_desafio_por_categoria(prompt, recientes)

# =========================================================
# 🚀 ENVÍO A TELEGRAM
# =========================================================

def enviar_a_telegram(mensaje: str):
    timestamp = datetime.now().strftime('%H:%M:%S')
    body = f"⏰ {timestamp}\n{mensaje}"
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=body)
    print(body)

# =========================================================
# 🔁 CICLO PRINCIPAL
# =========================================================

def ejecutar_ciclo_desafios():
    fecha = datetime.now().strftime("%Y-%m-%d")
    desafios = generar_desafios_diarios()

    if "Error" in desafios:
        enviar_a_telegram(f"⚠️ Error generando desafíos: {desafios['Error']}")
        guardar_historial(fecha, {"Error": desafios["Error"]})
        return

    header = f"🧭 Desafíos del día — {fecha}"
    enviar_a_telegram(header)

    for categoria, contenido in desafios.items():
        mensaje = f"📘 {categoria}:\n{contenido}"
        enviar_a_telegram(mensaje)
        time.sleep(3)

    # 👉 Guardado robusto y atómico
    guardar_historial(fecha, desafios)

# =========================================================
# 🏁 EJECUCIÓN
# =========================================================

if __name__ == "__main__":
    print("🧠 Iniciando ciclo de desafíos diarios...")
    ejecutar_ciclo_desafios()
    print("✅ Envío completado.")
