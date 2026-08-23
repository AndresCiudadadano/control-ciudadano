"""
Export a JSON - Control Ciudadano
===================================
Lee control_ciudadano.db (poblado por etl_diputados.py + etl_senado.py) y
genera legisladores.json en el formato EXACTO que espera src/App.jsx:

{
  "legisladores": [
    {
      "id": "dip-<persona_id>" | "sen-<senador_id>",
      "nombre": "...",
      "camara": "Diputados" | "Senado",
      "provinciaId": "<slug igual al id usado en PROVINCES dentro de App.jsx>",
      "bloque": "...",
      "asistencia": 0-100,                  // % redondeado
      "presentesCount": N,
      "ausentesCount": N,
      "sesiones": { "<sesionId>": "presente" | "ausente", ... },
      "votos": { "<votacionId>": "afirmativo"|"negativo"|"abstencion"|"ausente", ... },
      "proyectos": ["Título del proyecto", ...]   // best-effort, ver aviso abajo
    }, ...
  ],
  "votaciones": [ { "id": "...", "titulo": "...", "fecha": "..." }, ... ],
  "sesiones":   [ { "id": "...", "fecha": "...", "tipo": "..." }, ... ]
}

DECISIONES DE DISEÑO (importantes, leer antes de confiar ciegamente en los datos):

1. Un legislador solo tiene entradas en sus diccionarios "sesiones"/"votos"
   para las sesiones/votaciones donde HCDN o el Senado tienen un registro
   real de él (es decir, donde efectivamente era miembro en ese momento).
   Esto evita marcarlo "ausente" en años anteriores a su propio mandato.
   El App.jsx ya filtra su vista de detalle usando exactamente estas claves,
   así que esto es consistente extremo a extremo.

2. Diputados: cada "sesión" (para asistencia) es un agrupado por
   (período, reunión) — una reunión puede tener varias actas/votaciones
   nominales adentro. Se considera "presente" en la sesión si votó
   afirmativo/negativo/abstención en AL MENOS UNA acta de esa reunión;
   si todos sus registros en esa reunión son "ausente", se marca ausente.
   Cada acta individual, en cambio, es una "votación" separada (para la
   lista de "Votos recientes").

3. Senado: la API de ArgentinaDatos no distingue sesión de votación — cada
   acta ya es ambas cosas (trae presentes/ausentes agregados). Se usa el
   mismo acta_id como id de sesión y de votación.

4. "proyectos": la API de Senado usada acá no expone autoría de proyectos,
   así que ese array queda vacío para Senado. Para Diputados, se intenta
   cruzar por nombre de autor contra el dataset de expedientes (best-effort,
   puede fallar si el nombre no está escrito exactamente igual).

Uso:
    python etl_diputados.py
    python etl_senado.py
    python export_to_json.py
"""

import json
import re
import sqlite3
import unicodedata
from collections import defaultdict
from pathlib import Path

DB_PATH = Path("control_ciudadano.db")
OUT_PATH = Path("control-ciudadano-app/public/data/legisladores.json")

VOTO_MAP = {
    "AFIRMATIVO": "afirmativo", "AFIRMATIVA": "afirmativo", "SI": "afirmativo",
    "NEGATIVO": "negativo", "NEGATIVA": "negativo", "NO": "negativo",
    "ABSTENCION": "abstencion", "ABSTENCIÓN": "abstencion",
    "AUSENTE": "ausente", "AUSENTE C/AVISO": "ausente", "AUSENTE S/AVISO": "ausente",
}


def normalize_voto(valor) -> str:
    if not isinstance(valor, str):
        return "ausente"
    key = unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode().strip().upper()
    if key in VOTO_MAP:
        return VOTO_MAP[key]
    if "AUSEN" in key:
        return "ausente"
    if "AFIRM" in key:
        return "afirmativo"
    if "NEGAT" in key:
        return "negativo"
    if "ABSTEN" in key:
        return "abstencion"
    return "ausente"


def normalize_nombre(valor) -> str:
    if not isinstance(valor, str):
        return ""
    norm = unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^A-Za-z ]", " ", norm.upper()).split())


def table_exists(conn, name: str) -> bool:
    return conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def build_diputados(conn):
    """Devuelve (legisladores[], sesiones[], votaciones[]) para Diputados.
    Listas vacías si el ETL de Diputados no corrió todavía."""
    if not table_exists(conn, "legisladores"):
        print("AVISO: faltan tablas de Diputados — corré etl_diputados.py primero.")
        return [], [], []

    conn.row_factory = sqlite3.Row
    legs = [dict(r) for r in conn.execute("SELECT * FROM legisladores WHERE camara='diputados'")]
    sesiones_raw = {r["acta_id"]: dict(r) for r in conn.execute("SELECT * FROM sesiones")}
    votos_raw = [dict(r) for r in conn.execute("SELECT * FROM votos")]
    proyectos_raw = [dict(r) for r in conn.execute("SELECT * FROM proyectos")] if table_exists(conn, "proyectos") else []

    # Agrupar actas en "reuniones" (periodo+reunion) para la asistencia
    reunion_de_acta = {}
    for acta_id, s in sesiones_raw.items():
        reunion_de_acta[acta_id] = f"dip-r{s.get('periodo')}-{s.get('reunion')}"

    reuniones_meta = {}  # reunion_key -> {fecha, tipo}
    for acta_id, s in sesiones_raw.items():
        rk = reunion_de_acta[acta_id]
        fecha = s.get("fecha") or ""
        if rk not in reuniones_meta or fecha < (reuniones_meta[rk]["fecha"] or ""):
            reuniones_meta[rk] = {"fecha": s.get("fecha"), "tipo": s.get("tipo_sesion")}

    votaciones = [
        {"id": f"dip-{acta_id}", "titulo": s.get("titulo") or f"Acta {acta_id}", "fecha": s.get("fecha")}
        for acta_id, s in sesiones_raw.items()
    ]
    sesiones = [
        {"id": rk, "fecha": meta["fecha"], "tipo": meta["tipo"]}
        for rk, meta in reuniones_meta.items()
    ]

    votos_por_persona = defaultdict(list)
    for v in votos_raw:
        votos_por_persona[v["persona_id"]].append(v)

    # Proyectos: cruce best-effort por nombre de autor
    proyectos_por_autor_norm = defaultdict(list)
    for p in proyectos_raw:
        autor_norm = normalize_nombre(p.get("autor"))
        if autor_norm and p.get("titulo"):
            proyectos_por_autor_norm[autor_norm].append(p["titulo"])

    legisladores = []
    for leg in legs:
        persona_id = leg["persona_id"]
        mis_votos = votos_por_persona.get(persona_id, [])

        votos_dict = {}
        reunion_estado = {}  # reunion_key -> True si presente en al menos un acta
        for v in mis_votos:
            acta_id = v["acta_id"]
            estado = normalize_voto(v.get("voto"))
            votos_dict[f"dip-{acta_id}"] = estado
            rk = reunion_de_acta.get(acta_id)
            if rk:
                reunion_estado[rk] = reunion_estado.get(rk, False) or (estado != "ausente")

        sesiones_dict = {rk: ("presente" if presente else "ausente") for rk, presente in reunion_estado.items()}
        presentes = sum(1 for v in sesiones_dict.values() if v == "presente")
        total = len(sesiones_dict)

        nombre_norm = normalize_nombre(leg.get("nombre"))
        proyectos = proyectos_por_autor_norm.get(nombre_norm, [])

        legisladores.append({
            "id": f"dip-{persona_id}",
            "nombre": leg.get("nombre"),
            "camara": "Diputados",
            "provinciaId": leg.get("provincia_slug") or "desconocida",
            "bloque": leg.get("bloque_actual"),
            "asistencia": round(100 * presentes / total) if total else 0,
            "presentesCount": presentes,
            "ausentesCount": total - presentes,
            "sesiones": sesiones_dict,
            "votos": votos_dict,
            "proyectos": proyectos,
        })

    return legisladores, sesiones, votaciones


def build_senado(conn):
    """Devuelve (legisladores[], sesiones[], votaciones[]) para Senado.
    Listas vacías si el ETL de Senado no corrió todavía."""
    if not table_exists(conn, "legisladores_senado"):
        print("AVISO: faltan tablas de Senado — corré etl_senado.py primero.")
        return [], [], []

    conn.row_factory = sqlite3.Row
    sens = [dict(r) for r in conn.execute("SELECT * FROM legisladores_senado")]
    sesiones_raw = {r["acta_id"]: dict(r) for r in conn.execute("SELECT * FROM sesiones_senado")}
    votos_raw = [dict(r) for r in conn.execute("SELECT * FROM votos_senado")]

    votaciones = [
        {"id": f"sen-{acta_id}", "titulo": s.get("titulo") or f"Acta {acta_id}", "fecha": s.get("fecha")}
        for acta_id, s in sesiones_raw.items()
    ]
    # En Senado cada acta es a la vez sesión y votación (ver docstring)
    sesiones = [
        {"id": f"sen-{acta_id}", "fecha": s.get("fecha"), "tipo": None}
        for acta_id, s in sesiones_raw.items()
    ]

    votos_por_nombre = defaultdict(list)
    for v in votos_raw:
        votos_por_nombre[v["nombre_norm"]].append(v)

    legisladores = []
    for sen in sens:
        nombre_norm = sen["nombre_norm"]
        mis_votos = votos_por_nombre.get(nombre_norm, [])

        votos_dict = {}
        sesiones_dict = {}
        for v in mis_votos:
            acta_id = v["acta_id"]
            estado = normalize_voto(v.get("voto"))
            key = f"sen-{acta_id}"
            votos_dict[key] = estado
            sesiones_dict[key] = "presente" if estado != "ausente" else "ausente"

        presentes = sum(1 for v in sesiones_dict.values() if v == "presente")
        total = len(sesiones_dict)

        legisladores.append({
            "id": f"sen-{sen.get('senador_id')}",
            "nombre": sen.get("nombre"),
            "camara": "Senado",
            "provinciaId": sen.get("provincia_slug") or "desconocida",
            "bloque": sen.get("bloque") or sen.get("partido"),
            "asistencia": round(100 * presentes / total) if total else 0,
            "presentesCount": presentes,
            "ausentesCount": total - presentes,
            "sesiones": sesiones_dict,
            "votos": votos_dict,
            "proyectos": [],  # no disponible en la fuente usada, ver docstring
        })

    return legisladores, sesiones, votaciones


def main():
    if not DB_PATH.exists():
        print(f"ERROR: no existe {DB_PATH}. Corré primero etl_diputados.py y/o etl_senado.py.")
        return

    conn = sqlite3.connect(DB_PATH)
    leg_dip, ses_dip, vot_dip = build_diputados(conn)
    leg_sen, ses_sen, vot_sen = build_senado(conn)
    conn.close()

    salida = {
        "legisladores": leg_dip + leg_sen,
        "sesiones": ses_dip + ses_sen,
        "votaciones": vot_dip + vot_sen,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)

    print(f"Listo: {OUT_PATH}")
    print(f"  Diputados: {len(leg_dip)} legisladores, {len(ses_dip)} sesiones, {len(vot_dip)} votaciones")
    print(f"  Senado:    {len(leg_sen)} legisladores, {len(ses_sen)} sesiones, {len(vot_sen)} votaciones")
    if not leg_dip:
        print("  -> falta correr etl_diputados.py")
    if not leg_sen:
        print("  -> falta correr etl_senado.py")


if __name__ == "__main__":
    main()
