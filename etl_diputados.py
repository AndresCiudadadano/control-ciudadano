"""
ETL - Cámara de Diputados (HCDN) - Control Ciudadano
=====================================================
Baja datos reales del portal de datos abiertos de HCDN (datos.hcdn.gob.ar)
usando la API de CKAN (datastore_search), con los resource_id confirmados
de cada dataset. Guarda todo normalizado en control_ciudadano.db (SQLite).

Requisitos:
    pip install requests pandas --break-system-packages

Uso:
    python etl_diputados.py

Si algo falla o vuelve vacío, correr con --debug para ver las columnas
reales que trajo cada dataset y ajustar el mapeo de columnas más abajo.
"""

import argparse
import io
import json
import re
import sqlite3
import sys
import time
import unicodedata
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://datos.hcdn.gob.ar/api/3/action/datastore_search"
RESOURCE_SHOW_URL = "https://datos.hcdn.gob.ar/api/3/action/resource_show"
DB_PATH = Path("control_ciudadano.db")
RAW_DIR = Path("data_raw")
RAW_DIR.mkdir(exist_ok=True)

# Resource IDs confirmados directamente en el portal CKAN de HCDN.
# Si HCDN publica un nuevo período, el resource_id cambia: buscar en
# https://datos.hcdn.gob.ar/dataset/<nombre-dataset> y actualizar acá.
RESOURCES = {
    "legisladores": "bed68ccd-81f4-4165-89b5-2b3ff9720cac",   # Composición actual de la Cámara
    "bloques": "02a14a9d-b868-4565-9a76-6f458e9227dd",         # Listado actual de Bloques
    "votos_detalle": "262cc543-3186-401b-b35e-dcdb2635976d",   # Votaciones nominales - detalle (per. 129-137)
    "votos_cabecera": "cbc1a4e1-5616-40d9-947e-22e567eba2f5",  # Votaciones nominales - cabecera (per. 129-137)
    "expedientes": "2f917f50-f5d6-4252-83d5-86a38b3d2987",     # Expedientes (per. 129-137)
}

PAGE_SIZE = 5000


def fetch_resource_direct_download(name: str, resource_id: str, debug: bool = False) -> pd.DataFrame:
    """Respaldo: cuando datastore_search no está activado para un resource
    (CKAN devuelve 404), se consulta resource_show para obtener la URL real
    del archivo (CSV o XLSX) y se descarga/parsea directo con pandas."""
    print(f"[{name}] el datastore no está activado para este resource — "
          f"probando descarga directa del archivo...")
    resp = requests.get(RESOURCE_SHOW_URL, params={"id": resource_id}, timeout=60)
    resp.raise_for_status()
    payload = resp.json()
    if not payload.get("success"):
        raise RuntimeError(f"[{name}] resource_show también falló: {payload}")

    file_url = payload["result"]["url"]
    fmt = (payload["result"].get("format") or "").upper()
    print(f"[{name}] descargando archivo directo: {file_url} (formato: {fmt or 'desconocido'})")

    if file_url.lower().endswith((".xlsx", ".xls")) or fmt in ("XLSX", "XLS"):
        df = pd.read_excel(file_url)
    elif file_url.lower().endswith(".json") or fmt == "JSON":
        # El archivo puede traer un BOM al principio: decodificar con utf-8-sig
        raw_bytes = requests.get(file_url, timeout=120).content
        raw = json.loads(raw_bytes.decode("utf-8-sig"))
        if isinstance(raw, list):
            df = pd.DataFrame(raw)
        elif isinstance(raw, dict):
            df = None
            for key in ("data", "records", "result", "rows", "fields"):
                if key in raw and isinstance(raw[key], list):
                    df = pd.DataFrame(raw[key])
                    break
            if df is None and raw and all(isinstance(v, dict) for v in raw.values()):
                # Formato real observado en HCDN: {"1": {...fila...}, "2": {...fila...}, ...}
                # (diccionario numerado en vez de lista) — usar los valores como filas.
                df = pd.DataFrame(list(raw.values()))
            if df is None:
                if debug:
                    print(f"[{name}] AVISO: estructura JSON no reconocida, claves de primer nivel: {list(raw.keys())}")
                df = pd.DataFrame(raw)
        else:
            raise RuntimeError(f"[{name}] estructura JSON inesperada en {file_url}")
        # Algunos campos vienen con un BOM incrustado en el propio nombre (ej. "\ufeffacta_id")
        df.columns = [str(c).replace("\ufeff", "") for c in df.columns]
    else:
        # Probar con separadores/encodings comunes en datasets del Estado argentino
        try:
            df = pd.read_csv(file_url, sep=None, engine="python", encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(file_url, sep=None, engine="python", encoding="latin-1")

    if debug:
        print(f"[{name}] columnas reales (vía descarga directa): {list(df.columns)}")
    print(f"[{name}] {len(df)} filas descargadas directo del archivo.")
    return df


def fetch_resource(name: str, resource_id: str, debug: bool = False) -> pd.DataFrame:
    """Descarga un resource completo de CKAN, paginando de a PAGE_SIZE filas.
    Si el datastore_search no está activado para ese resource (404), cae
    automáticamente a descargar el archivo directo (ver fetch_resource_direct_download)."""
    cache_file = RAW_DIR / f"{name}.csv"
    if cache_file.exists():
        print(f"[{name}] usando caché en {cache_file}")
        return pd.read_csv(cache_file, low_memory=False)

    print(f"[{name}] descargando desde CKAN (resource_id={resource_id})...")
    records = []
    offset = 0
    while True:
        params = {"resource_id": resource_id, "limit": PAGE_SIZE, "offset": offset}
        resp = requests.get(BASE_URL, params=params, timeout=60)

        if resp.status_code == 404:
            # Este resource no tiene datastore activo: usar el respaldo de
            # descarga directa y devolver acá mismo (se cachea igual abajo).
            df = fetch_resource_direct_download(name, resource_id, debug=debug)
            df.to_csv(cache_file, index=False)
            print(f"[{name}] guardado {len(df)} filas en {cache_file}")
            return df

        resp.raise_for_status()
        payload = resp.json()

        if not payload.get("success"):
            print(f"[{name}] ERROR: la API respondió success=false: {payload}")
            break

        result = payload["result"]
        batch = result.get("records", [])
        records.extend(batch)

        if debug and offset == 0:
            print(f"[{name}] columnas reales: {list(batch[0].keys()) if batch else 'SIN DATOS'}")

        total = result.get("total", len(records))
        print(f"[{name}] {len(records)}/{total} filas...")

        if len(batch) < PAGE_SIZE or len(records) >= total:
            break
        offset += PAGE_SIZE
        time.sleep(0.2)  # no martillar la API

    df = pd.DataFrame.from_records(records)
    df.to_csv(cache_file, index=False)
    print(f"[{name}] guardado {len(df)} filas en {cache_file}")
    return df


def find_col(df: pd.DataFrame, *candidates: str) -> str | None:
    """Busca la primera columna cuyo nombre contenga alguno de los candidatos
    (case-insensitive, ignorando espacios/guiones bajos)."""
    normalized = {c: c.lower().replace(" ", "").replace("_", "") for c in df.columns}
    for cand in candidates:
        cand_norm = cand.lower().replace(" ", "").replace("_", "")
        for original, norm in normalized.items():
            if cand_norm in norm:
                return original
    return None


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
    import unicodedata
    norm = unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode().lower().strip()
    return PROVINCIA_SLUG.get(norm, norm.replace(" ", ""))


def _norm_nombre(v):
    """Normaliza un nombre: sin acentos, may\u00fascula, solo letras y espacios."""
    if not isinstance(v, str):
        return ""
    n = unicodedata.normalize("NFKD", v).encode("ascii", "ignore").decode()
    n = re.sub(r"[^A-Za-z ]", " ", n.upper())
    return " ".join(n.split())


def normalize_nombre_apellido_flexible(v):
    """Igual que _norm_nombre, pero ordena las palabras alfab\u00e9ticamente para
    que el cruce no dependa de si el nombre viene como 'Apellido Nombre' o
    'Nombre Apellido' (ej. la tabla de asistencia actual usa 'APELLIDO, Nombre',
    mientras el listado oficial separa Apellido y Nombre en columnas propias)."""
    return " ".join(sorted(_norm_nombre(v).split()))


ASISTENCIA_ACTUAL_URL = "https://votaciones.hcdn.gob.ar/estadisticas/home"


def fetch_asistencia_actual(debug: bool = False) -> pd.DataFrame:
    """Trae la tabla de asistencia del PERÍODO ACTUAL desde el sitio nuevo de
    votaciones electrónicas de HCDN (no el portal viejo de datos abiertos,
    que solo llega a 2018). Esta página ya trae, para cada diputado, el
    total acumulado de votos afirmativos/negativos/abstenciones/ausencias
    del período vigente — no hace falta scrapear acta por acta."""
    cache_file = RAW_DIR / "asistencia_actual.csv"
    if cache_file.exists():
        print("[asistencia_actual] usando caché en", cache_file)
        return pd.read_csv(cache_file)

    print(f"[asistencia_actual] descargando desde {ASISTENCIA_ACTUAL_URL} ...")
    resp = requests.get(ASISTENCIA_ACTUAL_URL, timeout=60, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    resp.raise_for_status()

    # Diagnóstico: guardamos el HTML crudo para poder inspeccionarlo si algo falla.
    raw_file = RAW_DIR / "asistencia_actual_raw.html"
    with open(raw_file, "w", encoding="utf-8") as f:
        f.write(resp.text)
    print(f"[asistencia_actual] HTML crudo guardado en {raw_file} ({len(resp.text)} caracteres, "
          f"contiene '<table': {'<table' in resp.text.lower()})")

    tablas = pd.read_html(io.StringIO(resp.text))
    if debug:
        print(f"[asistencia_actual] se encontraron {len(tablas)} tablas en la página")
        for i, t in enumerate(tablas):
            print(f"  tabla {i}: columnas={list(t.columns)}, filas={len(t)}")

    # Nos quedamos con la tabla más grande (la de todos los diputados)
    df = max(tablas, key=len)
    df.columns = [str(c).strip().upper() for c in df.columns]
    if debug:
        print("[asistencia_actual] columnas elegidas:", list(df.columns))
        print(df.head(3))

    df.to_csv(cache_file, index=False)
    print(f"[asistencia_actual] guardado {len(df)} filas en {cache_file}")
    return df


def build_database(dfs: dict, debug: bool = False):
    conn = sqlite3.connect(DB_PATH)

    # --- Asistencia del período ACTUAL (fuente nueva, no la vieja de 2011-2018) ---
    asistencia_actual_por_nombre = {}
    try:
        df_asis = fetch_asistencia_actual(debug=debug)
        col_dip = find_col(df_asis, "diputado")
        col_af = find_col(df_asis, "afirm")
        col_ne = find_col(df_asis, "neg")
        col_ab = find_col(df_asis, "abst")
        col_au = find_col(df_asis, "aus")
        if col_dip and col_af and col_ne and col_au:
            for _, fila_a in df_asis.iterrows():
                def _num(x):
                    try:
                        return int(str(x).replace("-", "0").strip() or 0)
                    except ValueError:
                        return 0
                af = _num(fila_a[col_af])
                ne = _num(fila_a[col_ne])
                ab = _num(fila_a[col_ab]) if col_ab else 0
                au = _num(fila_a[col_au])
                total = af + ne + ab + au
                clave = normalize_nombre_apellido_flexible(fila_a[col_dip])
                if clave and total:
                    asistencia_actual_por_nombre[clave] = {
                        "asistencia": round(100 * (af + ne + ab) / total),
                        "presentes": af + ne + ab,
                        "ausentes": au,
                        "total": total,
                    }
            print(f"[asistencia_actual] {len(asistencia_actual_por_nombre)} diputados con asistencia del período actual calculada")
        else:
            print("AVISO: no se encontraron las columnas esperadas en la tabla de asistencia actual "
                  "(columnas reales:", list(df_asis.columns), ") — la asistencia va a quedar sin datos.")
    except Exception as e:
        print(f"AVISO: no se pudo traer la asistencia del período actual ({e}) — sigue sin ese dato.")

    # --- legisladores ---
    df_leg = dfs["legisladores"]
    col_persona = find_col(df_leg, "persona_id", "personaid", "id_diputado", "idpersona")
    col_nombre = find_col(df_leg, "nombre", "apellido_nombre", "diputado")
    col_provincia = find_col(df_leg, "provincia", "distrito")
    col_bloque = find_col(df_leg, "bloque")
    col_apellido = find_col(df_leg, "apellido")
    col_mandato = find_col(df_leg, "mandato")
    col_fecha_inicio_real = find_col(df_leg, "fecha_de_inicio", "fecha_inicio")

    if debug:
        print("legisladores (listado oficial) -> apellido:", col_apellido, "| nombre:", col_nombre,
              "| provincia:", col_provincia, "| bloque:", col_bloque,
              "(este listado no trae persona_id — se usa solo para enriquecer mandato/fecha)")

    # El listado oficial de HCDN no tiene persona_id, así que no se puede usar
    # como tabla principal de legisladores. En cambio, se arma la tabla de
    # legisladores a partir de votos_detalle (que sí trae persona_id en cada
    # voto) y se enriquece con fecha de mandato del listado oficial cruzando
    # por nombre normalizado (best-effort).

    mandato_por_nombre = {}
    if col_apellido and col_nombre:
        for _, fila in df_leg.iterrows():
            clave = _norm_nombre(f"{fila[col_apellido]} {fila[col_nombre]}")
            mandato_por_nombre[clave] = {
                "mandato": fila[col_mandato] if col_mandato else None,
                "fecha_inicio": fila[col_fecha_inicio_real] if col_fecha_inicio_real else None,
            }

    # --- votaciones: detalle (voto por legislador) — se procesa antes que
    # "legisladores" porque de acá sale el persona_id real ---
    df_det = dfs["votos_detalle"]
    col_acta_d = find_col(df_det, "acta_id", "actaid")
    col_persona_d = find_col(df_det, "persona_id", "personaid")
    col_diputado_d = find_col(df_det, "diputado", "nombre")
    col_bloque_d = find_col(df_det, "bloque")
    col_provincia_d = find_col(df_det, "provincia", "distrito")
    col_voto = find_col(df_det, "voto")

    if debug:
        print("detalle -> acta:", col_acta_d, "| persona:", col_persona_d, "| voto:", col_voto)

    out_votos = pd.DataFrame({
        "acta_id": df_det[col_acta_d] if col_acta_d else None,
        "persona_id": df_det[col_persona_d] if col_persona_d else None,
        "diputado": df_det[col_diputado_d] if col_diputado_d else None,
        "bloque": df_det[col_bloque_d] if col_bloque_d else None,
        "provincia_raw": df_det[col_provincia_d] if col_provincia_d else None,
        "voto": df_det[col_voto] if col_voto else None,
    })
    out_votos["provincia_slug"] = out_votos["provincia_raw"].apply(slugify_provincia)

    # Verificar si persona_id realmente sirve como clave (a veces HCDN lo deja
    # vacío para la mayoría de las filas). Si no sirve, usamos el nombre
    # normalizado del diputado como identificador de respaldo.
    con_persona_id = out_votos["persona_id"].astype(str).str.strip()
    proporcion_con_id = (con_persona_id != "").mean() if len(out_votos) else 0
    if debug:
        print(f"votos: proporción de filas con persona_id no vacío: {proporcion_con_id:.1%}")

    if proporcion_con_id < 0.5:
        print("AVISO: persona_id viene vacío en la mayoría de los votos — "
              "se usa el nombre normalizado del diputado como identificador en su lugar.")
        out_votos["persona_id"] = out_votos["diputado"].apply(lambda v: "nom:" + _norm_nombre(v))

    out_votos.to_sql("votos", conn, if_exists="replace", index=False)
    print(f"votos: {len(out_votos)} filas")

    # IMPORTANTE: la base de "legisladores" es el LISTADO OFICIAL de la
    # Composición actual de la Cámara (df_leg, ~257 filas) — NO los votos.
    # Los votos cubren varios períodos históricos (129-137), así que usarlos
    # como base traía diputados que ya no están en su banca. Acá se cruza
    # cada diputado oficial actual con sus votos históricos (por nombre
    # normalizado) solo para poder calcular su asistencia.
    def _tokens(nombre_norm: str):
        return tuple(nombre_norm.split())

    votos_validos = out_votos.dropna(subset=["persona_id"])
    votos_validos = votos_validos[votos_validos["persona_id"].astype(str).str.strip() != ""]
    votos_validos = votos_validos.copy()
    votos_validos["nombre_norm"] = votos_validos["diputado"].apply(_norm_nombre)

    # Índice: para cada nombre único en los votos, probamos varias longitudes
    # de "apellido" (1 a 3 palabras) tanto AL PRINCIPIO como AL FINAL del
    # nombre (por si el formato es "Apellido Nombre" o "Nombre Apellido"),
    # y guardamos el resto de palabras junto al persona_id.
    from collections import defaultdict as _defaultdict
    indice_por_apellido = _defaultdict(list)  # apellido_tuple -> [(resto_tuple, persona_id)]
    nombres_unicos_votos = votos_validos.drop_duplicates(subset=["nombre_norm"])
    for _, fila_v in nombres_unicos_votos.iterrows():
        tokens = _tokens(fila_v["nombre_norm"])
        for n in range(1, min(3, len(tokens)) + 1):
            indice_por_apellido[tokens[:n]].append((tokens[n:], fila_v["persona_id"]))   # apellido al principio
            if len(tokens) > n:
                indice_por_apellido[tokens[-n:]].append((tokens[:-n], fila_v["persona_id"]))  # apellido al final

    if not col_apellido or not col_nombre:
        print("ERROR: no se pudo leer el listado oficial de diputados (faltan columnas "
              "de apellido/nombre). Revisar con --debug las columnas reales de 'legisladores'.")

    filas_leg = []
    sin_votos_matcheados = 0
    nombres_sin_match_reales = []  # rastreado durante el bucle, no reconstruido después
    sin_asistencia_actual = 0
    for _, fila in df_leg.iterrows():
        nombre_completo = f"{fila[col_apellido]} {fila[col_nombre]}" if col_apellido and col_nombre else fila.get(col_nombre)
        clave = _norm_nombre(nombre_completo)
        extra = mandato_por_nombre.get(clave, {})

        apellido_tokens = _tokens(_norm_nombre(fila[col_apellido])) if col_apellido else tuple()
        nombre_pila_tokens = set(_tokens(_norm_nombre(fila[col_nombre]))) if col_nombre else set()
        candidatos = indice_por_apellido.get(apellido_tokens, [])
        persona_id = None
        if candidatos:
            # Si hay más de una persona con ese mismo apellido en los votos,
            # nos quedamos con la que más coincide en nombre de pila.
            resto, pid = max(candidatos, key=lambda c: len(set(c[0]) & nombre_pila_tokens))
            persona_id = pid
        if persona_id is None:
            persona_id = "nom:" + clave
            sin_votos_matcheados += 1
            nombres_sin_match_reales.append(nombre_completo)

        clave_flexible = normalize_nombre_apellido_flexible(nombre_completo)
        asistencia = asistencia_actual_por_nombre.get(clave_flexible)
        if not asistencia:
            sin_asistencia_actual += 1

        filas_leg.append({
            "persona_id": persona_id,
            "nombre": nombre_completo,
            "camara": "diputados",
            "provincia_raw": fila[col_provincia] if col_provincia else None,
            "provincia_slug": slugify_provincia(fila[col_provincia] if col_provincia else None),
            "bloque_actual": fila[col_bloque] if col_bloque else None,
            "mandato_periodo": extra.get("mandato"),  # ej. "2025-2029"
            "mandato_inicio": extra.get("fecha_inicio"),
            "mandato_fin": None,
            "asistencia_actual": asistencia.get("asistencia") if asistencia else None,
            "presentes_actual": asistencia.get("presentes") if asistencia else None,
            "ausentes_actual": asistencia.get("ausentes") if asistencia else None,
            "total_votos_actual": asistencia.get("total") if asistencia else None,
        })
    print(f"[asistencia_actual] {len(filas_leg) - sin_asistencia_actual} de {len(filas_leg)} diputados "
          f"con asistencia del período actual matcheada")
    out_leg = pd.DataFrame(filas_leg)
    if out_leg.empty:
        out_leg = pd.DataFrame(columns=["persona_id", "nombre", "camara", "provincia_raw",
                                         "provincia_slug", "bloque_actual", "mandato_periodo",
                                         "mandato_inicio", "mandato_fin", "asistencia_actual",
                                         "presentes_actual", "ausentes_actual", "total_votos_actual"])
    out_leg.to_sql("legisladores", conn, if_exists="replace", index=False)
    print(f"legisladores: {len(out_leg)} filas (del listado OFICIAL de composición actual de la Cámara; "
          f"{sin_votos_matcheados} de ellos no matchearon con ningún voto histórico por nombre)")

    if sin_votos_matcheados:
        # Diagnóstico más fino: para una muestra de los que no matchearon,
        # buscamos si su apellido aparece como PALABRA COMPLETA (no como
        # substring de texto, que daba falsos positivos: "ALI" aparece
        # dentro de "ITALIA" sin ser el mismo apellido) en algún nombre de
        # los votos, y mostramos ese nombre real para ver la diferencia.
        nombre_por_token = _defaultdict(list)  # token -> [nombre_norm, ...] (nombres que contienen ese token)
        for nn in nombres_unicos_votos["nombre_norm"]:
            for tok in set(nn.split()):
                nombre_por_token[tok].append(nn)

        print(f"  Diagnóstico de los primeros 8 sin match (reales):")
        for nombre_completo in nombres_sin_match_reales[:8]:
            apellido_buscado = nombre_completo.split()[0].upper()
            import unicodedata as _ud2
            apellido_norm_buscado = _ud2.normalize("NFKD", apellido_buscado).encode("ascii", "ignore").decode()
            coincidencias = nombre_por_token.get(apellido_norm_buscado, [])
            if coincidencias:
                print(f"    '{nombre_completo}' -> apellido '{apellido_norm_buscado}' SÍ aparece como palabra "
                      f"en votos, ej.: {coincidencias[:2]}")
            else:
                print(f"    '{nombre_completo}' -> apellido '{apellido_norm_buscado}' NO aparece como palabra "
                      f"en ningún voto (probablemente sin votos registrados aún)")







    # --- votaciones: cabecera (sesiones) ---
    df_cab = dfs["votos_cabecera"]
    col_acta = find_col(df_cab, "acta_id", "actaid")
    col_periodo = find_col(df_cab, "nroperiodo", "periodo")
    col_reunion = find_col(df_cab, "reunion")
    col_sesion = find_col(df_cab, "sesion")
    col_tipo_sesion = find_col(df_cab, "tipo_sesion", "tiposesion")
    col_fecha = find_col(df_cab, "fecha")
    col_titulo = find_col(df_cab, "titulo", "asunto")
    col_resultado = find_col(df_cab, "resultado")
    col_afirm = find_col(df_cab, "votos_afirmativos", "afirmativos")
    col_negat = find_col(df_cab, "votos_negativos", "negativos")
    col_absten = find_col(df_cab, "abstenciones")
    col_ausentes = find_col(df_cab, "ausentes")

    if debug:
        print("cabecera -> acta:", col_acta, "| fecha:", col_fecha, "| titulo:", col_titulo)

    out_ses = pd.DataFrame({
        "acta_id": df_cab[col_acta] if col_acta else None,
        "periodo": df_cab[col_periodo] if col_periodo else None,
        "reunion": df_cab[col_reunion] if col_reunion else None,
        "sesion": df_cab[col_sesion] if col_sesion else None,
        "tipo_sesion": df_cab[col_tipo_sesion] if col_tipo_sesion else None,
        "fecha": df_cab[col_fecha] if col_fecha else None,
        "titulo": df_cab[col_titulo] if col_titulo else None,
        "resultado": df_cab[col_resultado] if col_resultado else None,
        "afirmativos": df_cab[col_afirm] if col_afirm else None,
        "negativos": df_cab[col_negat] if col_negat else None,
        "abstenciones": df_cab[col_absten] if col_absten else None,
        "ausentes": df_cab[col_ausentes] if col_ausentes else None,
    })
    out_ses.to_sql("sesiones", conn, if_exists="replace", index=False)
    print(f"sesiones: {len(out_ses)} filas")

    # --- expedientes (proyectos) ---
    df_exp = dfs["expedientes"]
    col_exp_id = find_col(df_exp, "expediente_id", "expediente", "numero_expediente")
    col_exp_titulo = find_col(df_exp, "titulo", "sumario", "asunto")
    col_exp_fecha = find_col(df_exp, "fecha")
    col_exp_tipo = find_col(df_exp, "tipo")
    col_exp_autor = find_col(df_exp, "autor", "firmante")
    col_exp_acta = find_col(df_exp, "acta_id", "actaid")

    out_proy = pd.DataFrame({
        "expediente_id": df_exp[col_exp_id] if col_exp_id else None,
        "titulo": df_exp[col_exp_titulo] if col_exp_titulo else None,
        "fecha": df_exp[col_exp_fecha] if col_exp_fecha else None,
        "tipo": df_exp[col_exp_tipo] if col_exp_tipo else None,
        "autor": df_exp[col_exp_autor] if col_exp_autor else None,
        "acta_id": df_exp[col_exp_acta] if col_exp_acta else None,
    })
    out_proy.to_sql("proyectos", conn, if_exists="replace", index=False)
    print(f"proyectos: {len(out_proy)} filas")

    conn.commit()
    conn.close()
    print(f"\nBase de datos generada en {DB_PATH}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="Imprime las columnas reales de cada dataset")
    parser.add_argument("--force", action="store_true", help="Ignora la caché en data_raw/ y vuelve a descargar todo")
    args = parser.parse_args()

    if args.force:
        for f in RAW_DIR.glob("*.csv"):
            f.unlink()

    dfs = {}
    for name, resource_id in RESOURCES.items():
        try:
            dfs[name] = fetch_resource(name, resource_id, debug=args.debug)
        except requests.RequestException as e:
            print(f"[{name}] ERROR de red: {e}")
            sys.exit(1)

    build_database(dfs, debug=args.debug)


if __name__ == "__main__":
    main()