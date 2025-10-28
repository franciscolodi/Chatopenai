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
    texto_corr = re.sub(r"'", '"_
