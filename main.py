# =========================================================
# 🧠 PROYECTO: Generador de desafíos diarios con IA (Groq API)
# =========================================================
# - Historial JSON con escritura atómica y backup si se corrompe
# - Parser JSON robusto para respuestas con ruido
# - Deduplicación de desafíos recientes por categoría
# - Envío a Telegram con logs
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
import sys

# =========================================================
# 🔧 CONFIGURACIÓN
# =========================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Puedes sobreescribir la ruta del historial con env var HIST_PATH
# Ej: HIST_PATH=".data/historial_desafios.json"
HIST_PATH = Path(os.getenv("HIST_PATH", "historial_desafios.json"))

# Parámetros de operación
MAX_REINTENTOS = int(os.getenv("MAX_REINTENTOS", "5"))   # reintentos del LLM
MAX_DIAS_HIST = int(os.getenv("MAX_DIAS_HIST", "30"))    # días a mantener en historial
PAUSA_ENTRE_MENSAJES = float(os.getenv("PAUSA_SEG", "2"))  # segundos entre mensajes Telegram

# Modo seco: no envía a Telegram ni llama a Groq (para pruebas locales)
DRY_RUN = os.getenv("DRY_RUN", "0") == "1"

# =========================================================
# ✅ VALIDACIONES BÁSICAS
# =========================================================

if not DRY_RUN:
    if not GROQ_API_KEY:
        raise RuntimeError("❌ Falta GROQ_API_KEY en variables de entorno.")
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("❌ Falta TELEGRAM_TOKEN o TELEGRAM_CHAT_ID en variables de entorno.")

# =========================================================
# 🚀 CLIENTES
# =========================================================

client = Groq(api_key=GROQ_API_KEY) if not DRY_RUN else None
bot = Bot(token=TELEGRAM_TOKEN) if not DRY_RUN else None

# =========================================================
# 🧩 UTILIDADES DE HISTORIAL (robustas y atómicas)
# =========================================================

def _escritura_atomica_json(path: Path, data: dict):
    """
    Escribe JSON de forma atómica:
    1) escribe en un archivo temporal
    2) fsync
    3) replace al destino
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"📝 Guardando historial en: {path.resolve()}")
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_name = tmp.name
    os.replace(tmp_name, path)
    print(f"✅ Historial escrito. Tamaño: {path.stat().st_size} bytes")

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
            print(f"⚠️ Historial inválido. Backup creado: {bak}")
        except Exception as e:
            print(f"⚠️ No se pudo crear backup del historial: {e}")

def cargar_historial() -> dict:
    """
    Carga un dict { 'YYYY-MM-DD': {...desafios...}, ... }
    Si el archivo no existe o está vacío, devuelve {}.
    Si está corrupto, hace backup y devuelve {}.
    """
    if not HIST_PATH.exists():
        print(f"ℹ️ No existe historial aún en {HIST_PATH.resolve()}")
        return {}
    try:
        texto = HIST_PATH.read_text(encoding="utf-8").strip()
        if not texto:
            print("ℹ️ Historial vacío, devolviendo {}")
            return {}
        data = json.loads(texto)
        if not isinstance(data, dict):
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
    Mantiene solo las últimas 'max_dias' fechas (ordenadas por fecha asc).
    """
    fechas = sorted(k for k in historial.keys() if re.fullmatch(r"\d{4}-\d{2}-\d{2}", k))
    if len(fechas) > max_dias:
        fechas = fechas[-max_dias:]
    return {k: historial[k] for k in fechas}

def guardar_historial(fecha: str, desafios: dict):
    """
    Guarda (o reemplaza) la entrada de una 'fecha' con escritura atómica, y
    conserva solo MAX_DIAS_HIST días. Verifica post-escritura.
    """
    try:
        historial = cargar_historial()
        historial[fecha] = desafios
        historial = _ordenar_y_recortar(historial, MAX_DIAS_HIST)
        _escritura_atomica_json(HIST_PATH, historial)

        # Verificación inmediata
        verif = cargar_historial()
        if fecha in verif:
            print(f"🔎 Verificado: {fecha} presente en historial ({len(verif)} días guardados).")
        else:
            print("❌ Verificación falló: fecha no encontrada tras guardar.")
    except Exception as e:
        print(f"❌ No se pudo guardar historial: {e}")

def obtener_desafios_recientes(dias: int = 5) -> dict:
    """
    Devuelve sets con textos recientes por categoría para evitar repeticiones.
    Estructura: {"CrossFit": set(), "Alimentación": set(), "Bienestar": set()}
    Ignora fechas con estructura inesperada.
    """
    historial = cargar_historial()
    # ordenamos y quedamos con los últimos N
    ordenado = _ordenar_y_recortar(historial, max_dias=max(len(historial), dias) or dias)
    ultimos_items = list(ordenado.items())[-dias:]

    recientes = {"CrossFit": set(), "Alimentación": set(), "Bienestar": set()}
    for _, dia in ultimos_items:
        if not isinstance(dia, dict):
            continue
        for cat in recientes.keys():
            if cat in dia and isinstance(dia[cat], str):
                recientes[cat].add(dia[cat])
    print(f"🧾 Desafíos recientes para evitar repeticiones: { {k: len(v) for k,v in recientes.items()} }")
    return recientes

# =========================================================
# 🧠 UTILIDAD PARA EXTRAER JSON ROBUSTO
# =========================================================

def extraer_json_robusto(texto: str):
    """
    Intenta extraer el primer objeto JSON '{}' del texto.
    - Intento directo
    - Normaliza comillas simples → dobles cuando parece JSON malformado.
    - Extrae el primer bloque {...} con DOTALL.
    - Repara escapes rotos mínimos y reintenta.
    """
    if not texto:
        return None

    # 1) Intento directo por si viene limpio
    try:
        return json.loads(texto)
    except Exception:
        pass

    # 2) Normalizar comillas simples → dobles (tolerante)
    texto_corr = re.sub(r"'", '"', texto)

    # 3) Tomar el primer dict que parezca JSON con DOTALL
    m = re.search(r"\{.*\}", texto_corr, flags=re.DOTALL)
    if not m:
        return None

    candidato = m.group(0)

    # 4) Quitar secuencias de escape rotas tipo \X no estándar
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
# 🧠 GENERADOR DE DESAFÍOS (Groq)
# =========================================================

def generar_desafio_por_categoria(prompt: str, recientes: dict) -> dict:
    if DRY_RUN:
        # Modo pruebas sin Groq
        print("🔬 DRY_RUN=1 → devolviendo desafíos dummy")
        return {
            "CrossFit": "5 series de 10 burpees con 60s de descanso.",
            "Alimentación": "Incluye 2 porciones de verduras de hoja verde en el almuerzo.",
            "Bienestar": "10 minutos de respiración diafragmática antes de dormir."
        }

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
            print(f"🧩 Respuesta LLM (recortada 200 chars): {contenido[:200]}{'...' if len(contenido)>200 else ''}")
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
# ✉️ ENVÍO A TELEGRAM
# =========================================================

def enviar_a_telegram(mensaje: str):
    timestamp = datetime.now().strftime('%H:%M:%S')
    body = f"⏰ {timestamp}\n{mensaje}"
    if DRY_RUN:
        print(f"[DRY_RUN] {body}")
        return
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=body)
    print(body)

# =========================================================
# 🔁 CICLO PRINCIPAL
# =========================================================

def ejecutar_ciclo_desafios():
    fecha = datetime.now().strftime("%Y-%m-%d")
    print(f"📅 Fecha de hoy: {fecha}")
    print(f"📂 Working dir: {os.getcwd()}")
    print(f"🗂 Archivo historial: {HIST_PATH.resolve()}")

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
        time.sleep(PAUSA_ENTRE_MENSAJES)

    # Guardado robusto y verificado
    guardar_historial(fecha, desafios)

# =========================================================
# 🧪 PRUEBA RÁPIDA DEL HISTORIAL (opcional)
# =========================================================

def prueba_historial_minima():
    print("=== PRUEBA HISTORIAL ===")
    fecha = datetime.now().strftime("%Y-%m-%d")
    dummy = {"CrossFit": "Test CF", "Alimentación": "Test Ali", "Bienestar": "Test Bien"}
    guardar_historial(fecha, dummy)
    data = cargar_historial()
    print(f"📦 Claves del historial (últimas 3): {list(data.keys())[-3:]}")
    print(f"📄 Ubicación: {HIST_PATH.resolve()}")
    print("=== FIN PRUEBA ===")

# =========================================================
# 🏁 EJECUCIÓN
# =========================================================

if __name__ == "__main__":
    print("🧠 Iniciando ciclo de desafíos diarios...")
    # Activa esta línea una sola vez si quieres validar guardado sin Groq/Telegram:
    # os.environ["DRY_RUN"] = "1"; DRY_RUN = True; prueba_historial_minima()
    try:
        ejecutar_ciclo_desafios()
        print("✅ Envío completado.")
    except Exception as e:
        print(f"💥 Error en ejecución principal: {e}")
        # En caso de error, deja una marca en el historial para diagnóstico
        fecha = datetime.now().strftime("%Y-%m-%d")
        try:
            guardar_historial(fecha, {"Error": f"MainException: {e}"})
        except Exception as e2:
            print(f"💥 Error adicional guardando historial tras excepción: {e2}")
        sys.exit(1)
