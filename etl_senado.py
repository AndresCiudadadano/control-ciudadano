"""
ETL - Senado de la Nación - Control Ciudadano
===============================================
Usa la API pública de ArgentinaDatos (api.argentinadatos.com), que normaliza
datos del Senado a partir de senado.gob.ar. Evita tener que scrapear HTML de
actas directamente (el sitio del Senado no tiene portal CKAN/API propia).

Fuente: https://argentinadatos.com/docs/operations/get-senado-senadores.html
        https://argentinadatos.com/docs/operations/get-senado-actas-a%C3%B1o.html

Requisitos:
    pip install requests --break-system-packages

Uso:
    python etl_senado.py
    python etl_senado.py --desde 2016 --hasta 2026   # rango de años a traer
    python etl_senado.py --debug                      # imprime la estructura cruda
"""

import argparse
import json
import sqlite3
import time
import unicodedata
from datetime import date
from pathlib import Path

import requests

BASE_URL = "https://api.argentinadatos.com/v1"
DB_PATH = Path("control_ciudadano.db")
RAW_DIR = Path("data_raw")
RAW_DIR.mkdir(exist_ok=True)

# La API solo tiene actas cargadas desde 2016. El límite superior lo ajustamos
# al año actual, ya que el máximo documentado (2026) puede ir corriéndose.
AÑO_MIN = 2016


PROVINCIA_SLUG = {
    "buenos aires": "buenosaires", "caba": "caba", "ciudad autonoma de buenos aires": "caba",
    "catamarca": "catamarca", "chaco": "chaco", "chubut": "chubut", "cordoba": "cordoba",
    "corrientes": "corrientes", "entre rios": "entrerios", "formosa": "formosa",
    "jujuy": "jujuy", "la pampa": "lapampa", "la rioja": "larioja", "mendoza": "mendoza",
    "misiones": "misiones", "neuquen": "neuquen", "rio negro": "rionegro",
    "salta": "salta", "san juan": "sanjuan", "san luis": "sanluis",
    "santa cruz": "santacruz", "santa fe": "santafe",
    "santiago del estero": "santiago", "tierra del fuego": "tierradelfuego",
    "tucuman": "tucuman",
}


def slugify_provincia(valor: str) -> str:
    if not isinstance(valor, str):
        return "desconocida"
    norm = unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode().lower().strip()
    return PROVINCIA_SLUG.get(norm, norm.replace(" ", ""))


def normalize_nombre(valor: str) -> str:
    """Clave de cruce entre el nombre en 'votos' (dentro del acta) y el nombre
    en la lista de senadores. La API no comparte un ID entre ambos, así que
    hay que matchear por nombre normalizado (sin acentos, mayúsculas, espacios)."""
    if not isinstance(valor, str):
        return ""
    norm = unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode()
    return " ".join(norm.upper().split())


def fetch_json(url: str, cache_name: str, debug: bool = False):
    cache_file = RAW_DIR / cache_name
    if cache_file.exists():
        with open(cache_file, encoding="utf-8") as f:
            return json.load(f)

    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    if debug:
        sample = data[0] if isinstance(data, list) and data else data
        print(f"[{cache_name}] estructura de ejemplo: {json.dumps(sample, ensure_ascii=False)[:500]}")

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return data


def fetch_senadores(debug: bool = False):
    print("[senadores] descargando...")
    data = fetch_json(f"{BASE_URL}/senado/senadores", "senadores.json", debug)
    print(f"[senadores] {len(data)} registros")
    return data


def fetch_actas(desde: int, hasta: int, debug: bool = False, force: bool = False):
    todas = []
    for año in range(desde, hasta + 1):
        cache_name = f"actas_{año}.json"
        if force:
            (RAW_DIR / cache_name).unlink(missing_ok=True)
        try:
            data = fetch_json(f"{BASE_URL}/senado/actas/{año}", cache_name, debug)
        except requests.HTTPError as e:
            print(f"[actas {año}] ERROR: {e} (puede que no haya actas ese año, se ignora)")
            continue
        print(f"[actas {año}] {len(data)} actas")
        todas.extend(data)
        time.sleep(0.2)
    return todas


def build_database(senadores: list, actas: list, debug: bool = False):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # --- tabla legisladores (senado) ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS legisladores_senado (
            senador_id TEXT, nombre TEXT, nombre_norm TEXT, provincia_raw TEXT,
            provincia_slug TEXT, partido TEXT, bloque TEXT,
            mandato_inicio TEXT, mandato_fin TEXT
        )
    """)
    cur.execute("DELETE FROM legisladores_senado")
    nombre_to_provincia = {}
    for s in senadores:
        nombre = s.get("nombre", "")
        nombre_norm = normalize_nombre(nombre)
        provincia_raw = s.get("provincia", "")
        provincia_slug = slugify_provincia(provincia_raw)
        nombre_to_provincia[nombre_norm] = provincia_slug
        periodo_legal = s.get("periodoLegal") or {}
        cur.execute(
            "INSERT INTO legisladores_senado VALUES (?,?,?,?,?,?,?,?,?)",
            (
                s.get("id"), nombre, nombre_norm, provincia_raw, provincia_slug,
                s.get("partido"), s.get("bloque"),
                periodo_legal.get("inicio"), periodo_legal.get("fin"),
            ),
        )
    print(f"legisladores_senado: {len(senadores)} filas")

    # --- tabla sesiones (senado) = actas, sin el detalle de voto ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sesiones_senado (
            acta_id INTEGER, titulo TEXT, proyecto TEXT, descripcion TEXT,
            fecha TEXT, resultado TEXT, miembros INTEGER, afirmativos INTEGER,
            negativos INTEGER, abstenciones INTEGER, presentes INTEGER, ausentes INTEGER
        )
    """)
    cur.execute("DELETE FROM sesiones_senado")

    # --- tabla votos (senado): explota el array 'votos' de cada acta ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS votos_senado (
            acta_id INTEGER, nombre TEXT, nombre_norm TEXT, voto TEXT, banca TEXT,
            provincia_slug TEXT
        )
    """)
    cur.execute("DELETE FROM votos_senado")

    sin_match = set()
    total_votos = 0
    for acta in actas:
        acta_id = acta.get("actaId")
        cur.execute(
            "INSERT INTO sesiones_senado VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                acta_id, acta.get("titulo"), acta.get("proyecto"), acta.get("descripcion"),
                acta.get("fecha"), acta.get("resultado"), acta.get("miembros"),
                acta.get("afirmativos"), acta.get("negativos"), acta.get("abstenciones"),
                acta.get("presentes"), acta.get("ausentes"),
            ),
        )
        for voto in acta.get("votos", []):
            nombre = voto.get("nombre", "")
            nombre_norm = normalize_nombre(nombre)
            provincia_slug = nombre_to_provincia.get(nombre_norm)
            if provincia_slug is None:
                sin_match.add(nombre)
            cur.execute(
                "INSERT INTO votos_senado VALUES (?,?,?,?,?,?)",
                (acta_id, nombre, nombre_norm, voto.get("voto"), voto.get("banca"), provincia_slug),
            )
            total_votos += 1

    print(f"sesiones_senado: {len(actas)} filas")
    print(f"votos_senado: {total_votos} filas")
    if sin_match:
        print(f"AVISO: {len(sin_match)} nombres en votos no matchearon con la lista de senadores "
              f"(mandatos vencidos, reemplazos, o diferencias de formato de nombre).")
        if debug:
            print("Ejemplos sin match:", list(sin_match)[:10])

    conn.commit()
    conn.close()
    print(f"\nBase de datos actualizada en {DB_PATH}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--desde", type=int, default=AÑO_MIN)
    parser.add_argument("--hasta", type=int, default=date.today().year)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--force", action="store_true", help="ignora la caché y vuelve a descargar todo")
    args = parser.parse_args()

    if args.force:
        for f in RAW_DIR.glob("*.json"):
            f.unlink()

    senadores = fetch_senadores(debug=args.debug)
    actas = fetch_actas(args.desde, args.hasta, debug=args.debug, force=args.force)
    build_database(senadores, actas, debug=args.debug)


if __name__ == "__main__":
    main()
