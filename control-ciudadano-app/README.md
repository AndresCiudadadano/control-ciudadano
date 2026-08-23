# Control Ciudadano

Monitor legislativo público: asistencia, votos y proyectos de diputados y
senadores nacionales, por provincia.

## Estructura

```
control-ciudadano-app/
├── src/App.jsx          ← componente principal (mapa + fichas)
├── public/data/         ← acá va legisladores.json (datos reales)
etl_diputados.py         ← baja datos de datos.hcdn.gob.ar
etl_senado.py             ← baja datos de la API de ArgentinaDatos
export_to_json.py         ← une ambos en public/data/legisladores.json
```

## 1. Correr el ETL (fuera de este proyecto, en la raíz)

```bash
pip install requests pandas --break-system-packages
python etl_diputados.py
python etl_senado.py
python export_to_json.py
```

Esto genera `control_ciudadano.db` y después `control-ciudadano-app/public/data/legisladores.json`.

Si `legisladores.json` no existe todavía, la web funciona igual pero muestra
datos de ejemplo (lo aclara arriba de todo, en el encabezado).

## 2. Correr en local

```bash
cd control-ciudadano-app
npm install
npm run dev
```

## 3. Publicar gratis (Vercel)

1. Subí esta carpeta a un repositorio de GitHub.
2. Entrá a vercel.com → "Add New Project" → importá el repo.
3. Framework preset: Vite (lo detecta solo). Deploy.
4. Te da un dominio gratis tipo `control-ciudadano.vercel.app`.

Cada vez que actualices el repo (por ejemplo, corriendo el ETL de nuevo y
subiendo el `legisladores.json` actualizado), Vercel redespliega solo.

## 4. Actualización automática (gratis, con GitHub Actions)

Ya viene incluido `.github/workflows/update-data.yml`: corre todos los días
a las 06:00 (hora Argentina), baja los datos nuevos de HCDN y Senado, los
exporta a `legisladores.json` y si hubo cambios los commitea solo. Ese commit
dispara el redeploy automático de Vercel — no hace falta que toques nada.

- Para cambiar la frecuencia, editá la línea `cron:` del archivo (formato cron estándar).
- También podés dispararlo a mano desde GitHub → pestaña "Actions" → "Actualizar datos legislativos" → "Run workflow".
- Si HCDN o Senado cambian el formato de sus datos y el ETL falla, el workflow
  no rompe el sitio (sigue sirviendo los últimos datos buenos) — revisá la
  pestaña "Actions" de tanto en tanto para ver si hay errores en rojo.

**Importante en Vercel:** como el sitio vive en la subcarpeta `control-ciudadano-app/`
dentro del repo, en la configuración del proyecto en Vercel tenés que poner
"Root Directory" = `control-ciudadano-app`.



- Dataset de "proyectos de ley" todavía no está enlazado a cada legislador
  como autor (el array `proyectos` queda vacío por ahora).
- Scraping de Senado depende de la API no oficial de ArgentinaDatos —
  si en algún momento el Senado publica un portal de datos abiertos propio,
  conviene migrar `etl_senado.py` a esa fuente oficial.
- Automatizar el ETL con un cron / GitHub Action para que se actualice solo
  (por ejemplo, una vez por semana).
