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
import json
import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://datos.hcdn.gob.ar/api/3/action/datastore_search"
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


def fetch_resource(name: str, resource_id: str, debug: bool = False) -> pd.DataFrame:
    """Descarga un resource completo de CKAN, paginando de a PAGE_SIZE filas."""
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


def build_database(dfs: dict, debug: bool = False):
    conn = sqlite3.connect(DB_PATH)

    # --- legisladores ---
    df_leg = dfs["legisladores"]
    col_persona = find_col(df_leg, "persona_id", "personaid", "id_diputado", "idpersona")
    col_nombre = find_col(df_leg, "nombre", "apellido_nombre", "diputado")
    col_provincia = find_col(df_leg, "provincia", "distrito")
    col_bloque = find_col(df_leg, "bloque")
    col_mandato_inicio = find_col(df_leg, "fecha_inicio", "inicio_mandato", "mandato_inicio")
    col_mandato_fin = find_col(df_leg, "fecha_fin", "fin_mandato", "mandato_fin")

    if debug:
        print("legisladores -> persona:", col_persona, "| nombre:", col_nombre,
              "| provincia:", col_provincia, "| bloque:", col_bloque)

    out_leg = pd.DataFrame({
        "persona_id": df_leg[col_persona] if col_persona else None,
        "nombre": df_leg[col_nombre] if col_nombre else None,
        "camara": "diputados",
        "provincia_raw": df_leg[col_provincia] if col_provincia else None,
        "bloque_actual": df_leg[col_bloque] if col_bloque else None,
        "mandato_inicio": df_leg[col_mandato_inicio] if col_mandato_inicio else None,
        "mandato_fin": df_leg[col_mandato_fin] if col_mandato_fin else None,
    })
    out_leg["provincia_slug"] = out_leg["provincia_raw"].apply(slugify_provincia)
    out_leg.to_sql("legisladores", conn, if_exists="replace", index=False)
    print(f"legisladores: {len(out_leg)} filas")

    # --- votaciones: cabecera (sesiones) ---
    df_cab = dfs["votos_cabecera"]
    col_acta = find_col(df_cab, "acta_id", "actaid")
    col_periodo = find_col(df_cab, "periodo")
    col_reunion = find_col(df_cab, "reunion")
    col_sesion = find_col(df_cab, "sesion")
    col_tipo_sesion = find_col(df_cab, "tipo_sesion", "tiposesion")
    col_fecha = find_col(df_cab, "fecha")
    col_titulo = find_col(df_cab, "titulo", "asunto")
    col_resultado = find_col(df_cab, "resultado")
    col_afirm = find_col(df_cab, "afirmativos", "votos_afirmativos")
    col_negat = find_col(df_cab, "negativos", "votos_negativos")
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

    # --- votaciones: detalle (voto por legislador) ---
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
    out_votos.to_sql("votos", conn, if_exists="replace", index=False)
    print(f"votos: {len(out_votos)} filas")

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
