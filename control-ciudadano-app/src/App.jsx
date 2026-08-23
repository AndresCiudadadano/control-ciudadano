import React, { useState, useMemo } from "react";

/* ============================================================
   MONITOR LEGISLATIVO — prototipo visual (datos de ejemplo)
   Paleta: cámara nocturna + sello de acta oficial
   ============================================================ */

const TOKENS = {
  bg: "#0E1826",
  bgAlt: "#0A121C",
  surface: "#152134",
  surfaceRaised: "#1B2A40",
  line: "#28374F",
  gold: "#C9A227",
  goldSoft: "#8F7A3E",
  sky: "#6EA8D6",
  textPrimary: "#EDEAE0",
  textMuted: "#8FA0B8",
  afirmativo: "#4C9A6A",
  negativo: "#C1502E",
  abstencion: "#D6A34E",
  ausente: "#5B6478",
};

const PROVINCES = [
  { id: "jujuy", name: "Jujuy" },
  { id: "salta", name: "Salta" },
  { id: "formosa", name: "Formosa" },
  { id: "catamarca", name: "Catamarca" },
  { id: "tucuman", name: "Tucumán" },
  { id: "chaco", name: "Chaco" },
  { id: "santiago", name: "Santiago del Estero" },
  { id: "misiones", name: "Misiones" },
  { id: "larioja", name: "La Rioja" },
  { id: "corrientes", name: "Corrientes" },
  { id: "santafe", name: "Santa Fe" },
  { id: "sanjuan", name: "San Juan" },
  { id: "entrerios", name: "Entre Ríos" },
  { id: "cordoba", name: "Córdoba" },
  { id: "sanluis", name: "San Luis" },
  { id: "caba", name: "CABA" },
  { id: "buenosaires", name: "Buenos Aires" },
  { id: "mendoza", name: "Mendoza" },
  { id: "lapampa", name: "La Pampa" },
  { id: "neuquen", name: "Neuquén" },
  { id: "rionegro", name: "Río Negro" },
  { id: "chubut", name: "Chubut" },
  { id: "santacruz", name: "Santa Cruz" },
  { id: "tierradelfuego", name: "Tierra del Fuego" },
];

// Contornos reales, extraídos automáticamente (detección de contornos por color)
// a partir de un mapa político provisto por el usuario. Coordenadas normalizadas a un viewBox de 300×628.
const PROVINCE_SHAPES = {
  jujuy: { path: "M88.8,0.0L88.2,3.0L85.8,6.0L79.8,7.8L79.2,11.4L75.0,13.2L75.0,15.6L73.2,18.0L73.2,30.6L72.0,35.4L82.2,43.8L84.0,42.6L96.6,42.6L99.6,47.4L107.4,48.6L109.2,50.4L115.2,50.4L119.4,48.0L122.4,43.8L122.4,31.8L111.0,31.2L107.4,26.4L107.4,22.2L105.6,22.2L104.4,20.4L105.0,5.4L95.4,4.8Z", cx: 95.7, cy: 26.8 },
  salta: { path: "M154.8,13.2L149.4,9.6L147.0,4.2L128.4,4.2L126.6,7.2L106.8,6.0L105.0,13.8L111.6,29.4L124.2,32.4L124.2,45.6L120.6,49.8L99.0,49.2L91.2,39.6L91.2,32.4L86.4,30.0L85.8,39.0L71.4,37.2L69.0,42.6L54.6,48.6L49.8,56.4L53.4,63.0L78.6,64.2L79.8,76.2L85.2,84.6L87.0,82.8L116.4,82.2L121.2,71.4L135.6,71.4L154.2,48.6Z", cx: 103.7, cy: 42.6 },
  formosa: { path: "M156.6,14.4L156.0,43.2L164.4,47.4L169.8,52.8L173.4,53.4L177.6,59.4L187.2,66.0L190.8,73.2L198.0,78.6L199.8,82.8L203.4,84.0L205.2,87.0L210.0,87.6L220.2,97.8L223.2,87.0L234.0,74.4L231.6,67.8L214.2,59.4L194.4,43.8L188.4,43.8L177.6,39.6L173.4,33.6L169.2,31.8L160.8,23.4Z", cx: 190.8, cy: 59.7 },
  chaco: { path: "M155.4,45.0L155.4,49.8L138.0,71.4L165.0,73.2L163.8,117.0L210.0,118.8L210.6,109.2L214.8,106.8L214.8,103.2L219.0,99.0L209.4,89.4L204.0,88.2L202.8,85.8L199.2,84.6L197.4,80.4L189.6,74.4L186.0,67.2L176.4,60.6L172.8,55.2L169.2,54.6L163.2,48.6Z", cx: 186.5, cy: 80.1 },
  tucuman: { path: "M117.0,84.0L107.4,84.0L104.4,82.8L103.2,81.0L98.4,81.0L98.4,83.4L97.2,84.6L91.8,84.6L90.6,87.6L91.8,88.8L91.8,101.4L90.6,103.2L93.6,105.0L94.2,109.2L95.4,111.6L98.4,113.4L99.0,115.8L101.4,114.0L107.4,114.0L108.0,112.8L108.0,105.6L110.4,103.2L113.4,96.0L113.4,93.0L115.2,91.2L116.4,91.2L116.4,84.6Z", cx: 102.7, cy: 96.6 },
  catamarca: { path: "M50.4,64.2L48.6,68.4L49.8,100.2L45.6,100.8L40.8,112.2L51.6,112.2L52.2,115.8L60.6,118.8L61.8,122.4L82.8,123.0L87.6,132.6L96.6,139.8L102.0,155.4L105.6,154.8L108.6,151.8L109.2,145.2L106.2,136.8L105.0,115.2L96.6,114.6L92.4,110.4L93.6,93.0L90.0,89.4L89.4,83.4L82.8,82.8L82.2,66.0L58.8,66.0Z", cx: 78.9, cy: 110.6 },
  misiones: { path: "M293.4,79.2L290.4,80.4L286.8,80.4L285.6,91.2L283.8,96.0L282.0,97.2L282.0,99.0L274.8,104.4L270.6,105.0L270.0,106.8L267.0,108.6L266.4,111.6L260.4,111.6L259.8,112.8L261.6,117.0L261.6,120.0L262.8,123.6L264.6,125.4L267.6,124.8L271.2,121.2L273.6,121.2L274.8,119.4L277.2,118.8L278.4,116.4L288.6,113.4L290.4,111.0L296.4,109.2L298.2,105.6L298.2,99.0L300.0,93.6L298.2,88.8L297.6,82.2Z", cx: 279.2, cy: 106.1 },
  santiago: { path: "M122.4,72.0L118.2,81.6L118.2,92.4L115.2,94.8L112.2,103.8L109.8,106.2L109.2,114.6L106.8,115.2L108.6,140.4L111.0,144.6L124.2,144.6L127.2,147.0L132.0,147.0L138.0,150.0L152.4,150.0L154.8,154.8L162.0,118.8L163.2,74.4Z", cx: 127.0, cy: 119.6 },
  corrientes: { path: "M258.6,111.0L237.6,111.6L226.2,107.4L216.6,107.4L212.4,109.8L211.8,118.8L207.6,123.6L207.0,132.0L204.6,139.8L198.0,145.2L195.6,162.6L217.8,161.4L222.6,169.8L226.8,165.0L226.8,162.6L229.8,161.4L234.0,155.4L238.8,153.0L244.8,145.2L249.6,141.6L251.4,137.4L255.6,135.0L256.8,132.0L262.2,130.2L262.8,126.0L260.4,122.4Z", cx: 231.4, cy: 137.2 },
  larioja: { path: "M40.8,114.0L33.0,124.8L37.8,126.0L43.2,133.2L43.8,146.4L54.6,148.2L66.6,159.0L75.0,169.8L75.0,180.0L81.0,189.0L94.8,189.0L95.4,173.4L100.8,158.4L94.8,140.4L85.8,133.2L85.8,130.2L81.0,124.2L76.2,122.4L74.4,123.6L61.2,123.6L59.4,120.0L56.4,120.0L51.0,117.0L51.0,112.8Z", cx: 67.5, cy: 140.8 },
  santafe: { path: "M208.8,120.6L163.8,118.8L156.0,160.2L157.2,179.4L153.0,195.6L157.8,202.2L157.8,214.2L142.2,237.0L158.4,238.2L171.0,224.4L177.6,224.4L180.0,220.8L175.2,211.2L175.8,190.8L186.0,182.4L193.8,171.0L196.2,145.2L198.0,141.6L202.8,139.2L205.8,122.4Z", cx: 175.9, cy: 182.0 },
  sanjuan: { path: "M32.4,126.0L30.6,138.0L27.0,141.6L28.8,148.8L28.8,162.0L24.6,164.4L22.8,176.4L20.4,177.6L19.2,182.4L20.4,187.8L23.4,190.8L24.0,198.0L33.0,196.8L34.2,194.4L46.2,194.4L46.8,198.0L51.6,195.6L69.0,195.6L70.2,189.0L79.2,189.0L74.4,183.0L74.4,174.6L72.6,168.6L64.8,159.0L54.0,149.4L43.2,147.6L43.2,135.6L38.4,128.4Z", cx: 42.8, cy: 171.2 },
  cordoba: { path: "M109.8,147.0L109.8,152.4L106.8,156.0L102.6,157.2L96.6,175.2L96.6,189.0L104.4,193.2L105.6,196.8L109.2,197.4L109.2,209.4L106.8,214.8L106.8,247.8L131.4,248.4L132.0,237.6L140.4,237.0L158.4,211.8L153.6,198.6L153.6,184.2L157.8,169.2L154.8,165.6L152.4,151.8L134.4,151.2L132.6,148.8L127.2,148.8L121.8,144.6Z", cx: 124.6, cy: 185.4 },
  entrerios: { path: "M211.8,161.4L203.4,163.8L196.2,163.8L195.6,170.4L188.4,181.8L181.8,189.0L178.2,189.6L175.8,202.2L176.4,208.2L178.8,214.2L190.8,225.0L201.0,229.2L205.8,233.4L208.8,233.4L208.8,222.6L210.6,217.2L211.8,216.0L214.8,216.0L214.8,204.6L216.6,202.2L216.6,193.2L218.4,192.0L219.6,184.2L223.2,175.2L223.2,172.8L218.4,164.4Z", cx: 203.4, cy: 197.1 },
  sanluis: { path: "M70.8,190.2L70.8,197.4L73.8,205.8L74.4,217.8L80.4,229.2L80.4,238.2L84.6,247.2L84.6,261.6L83.4,267.0L105.0,267.0L105.0,214.2L106.8,212.4L108.6,199.2L104.4,198.6L103.2,195.0L96.6,190.8Z", cx: 89.5, cy: 220.7 },
  mendoza: { path: "M40.8,193.2L36.0,195.0L33.0,198.6L25.2,199.8L28.2,208.2L28.2,215.4L31.8,217.2L31.8,235.8L27.6,242.4L25.8,252.6L23.4,255.0L25.2,258.6L25.8,271.2L37.8,289.2L45.6,289.8L47.4,292.8L57.6,295.8L57.0,267.6L81.6,266.4L83.4,251.4L79.2,241.2L79.2,231.0L72.6,218.4L72.0,205.8L69.0,197.4L61.8,196.8L59.4,194.4L43.8,195.0Z", cx: 47.5, cy: 234.9 },
  buenosaires: { path: "M182.4,220.8L178.8,225.0L172.2,225.0L159.6,238.8L133.8,238.2L130.2,357.0L138.0,363.0L147.6,354.0L148.8,325.8L173.4,325.2L207.0,318.6L216.6,313.2L217.2,309.0L231.6,291.6L232.2,282.6L225.6,278.4L226.8,261.6L219.6,253.2L209.4,247.8L209.4,235.2L204.6,235.2Z", cx: 188.8, cy: 280.9 },
  lapampa: { path: "M58.8,268.8L59.4,297.0L66.0,298.8L66.0,306.6L69.6,309.6L75.0,309.6L84.6,318.6L114.0,321.0L129.6,330.6L131.4,250.2L106.8,250.2L106.2,268.8Z", cx: 89.0, cy: 294.2 },
  neuquen: { path: "M24.6,272.4L22.2,273.0L21.0,277.8L16.8,279.0L15.0,283.2L15.6,301.8L18.6,307.8L18.6,322.2L13.8,325.8L13.8,335.4L10.2,339.6L8.4,360.0L9.6,364.8L16.8,364.8L19.2,363.0L20.4,356.4L31.2,354.0L33.0,351.0L33.6,343.8L48.0,333.6L55.2,324.6L61.2,323.4L58.2,318.6L57.6,297.6L46.8,294.0L44.4,291.0L37.2,291.0L34.2,288.0L34.2,285.0L25.2,276.0Z", cx: 28.8, cy: 316.6 },
  rionegro: { path: "M9.6,377.4L12.0,382.8L104.4,380.4L105.6,361.8L119.4,361.8L124.8,365.4L136.2,363.6L129.0,358.2L129.0,332.4L114.0,322.8L83.4,319.8L74.4,310.8L66.6,309.0L64.2,298.8L59.4,298.8L60.0,324.6L35.4,345.6L34.8,352.8L31.8,356.4L22.2,358.2L19.2,366.6L9.6,366.6Z", cx: 70.2, cy: 346.1 },
  chubut: { path: "M123.6,384.6L107.4,385.2L105.0,382.2L13.2,384.6L8.4,388.2L9.0,403.2L12.0,405.6L12.0,411.6L14.4,413.4L15.0,437.4L12.0,439.2L17.4,439.8L16.8,455.4L18.6,458.4L70.8,456.6L79.2,442.8L87.6,438.0L96.6,438.0L96.6,431.4L102.0,425.4L102.0,410.4L105.6,404.4L112.8,400.8L113.4,397.2L120.6,397.2L124.8,394.8Z", cx: 65.3, cy: 416.4 },
  santacruz: { path: "M70.2,458.4L18.6,460.8L16.2,463.2L15.6,484.8L12.0,488.4L10.2,496.2L10.2,515.4L0.0,529.2L6.6,550.8L17.4,551.4L18.0,565.8L24.0,573.0L48.6,572.4L62.4,576.0L54.6,558.0L54.6,543.6L57.6,538.8L69.0,532.2L72.0,514.2L91.8,495.6L94.8,485.4L93.0,478.8L81.6,477.0L72.6,468.0Z", cx: 44.6, cy: 515.7 },
  tierradelfuego: { path: "M63.0,586.2L64.2,625.2L78.6,625.2L84.0,626.4L87.0,628.2L88.8,627.0L96.0,626.4L97.2,625.2L107.4,625.2L108.0,624.0L112.2,624.0L100.8,624.0L99.6,621.6L91.8,621.6L87.0,619.2L82.2,613.8L76.2,610.2L70.2,603.6L67.8,597.6L65.4,597.0L65.4,589.8Z", cx: 85.4, cy: 616.3 },
};

// CABA no viene separada en el mapa fuente (queda dentro de Buenos Aires) — se marca aparte
const CABA_MARKER = { cx: 197, cy: 233 };

const VIEW_W = 300;
const VIEW_H = 629;

const NAMES = [
  "Marta Ibáñez", "Rodrigo Ponce", "Elena Suárez", "Diego Farías",
  "Lucía Ortega", "Martín Zabala", "Carla Reinoso", "Facundo Aráoz",
  "Julieta Cano", "Ignacio Bravo", "Paula Merlo", "Tomás Ibarra",
  "Noelia Guzmán", "Andrés Peralta", "Silvina Roca", "Gastón Villalba",
  "Camila Sosa", "Emiliano Duarte", "Verónica Leiva", "Nahuel Correa",
  "Agustina Pardo", "Federico Nuñez", "Rocío Aguirre", "Bruno Escobar",
];

const BLOQUES = ["UP", "LLA", "PRO", "UCR", "Hacemos", "Federal", "Independencia"];

const VOTACIONES_EJEMPLO = [
  { id: "v1", titulo: "Presupuesto Nacional 2026", fecha: "12 mar 2026" },
  { id: "v2", titulo: "Boleta Única de Papel", fecha: "2 abr 2026" },
  { id: "v3", titulo: "Modificación Ley de Alquileres", fecha: "20 may 2026" },
  { id: "v4", titulo: "Promoción Industrial NEA", fecha: "15 jun 2026" },
];

// Sesiones del período — cada una con fecha exacta y tipo
const SESIONES_EJEMPLO = [
  { id: "s1", fecha: "5 mar 2026", tipo: "Ordinaria" },
  { id: "s2", fecha: "12 mar 2026", tipo: "Ordinaria" },
  { id: "s3", fecha: "2 abr 2026", tipo: "Ordinaria" },
  { id: "s4", fecha: "23 abr 2026", tipo: "Ordinaria" },
  { id: "s5", fecha: "20 may 2026", tipo: "Ordinaria" },
  { id: "s6", fecha: "4 jun 2026", tipo: "Extraordinaria" },
  { id: "s7", fecha: "15 jun 2026", tipo: "Ordinaria" },
  { id: "s8", fecha: "29 jun 2026", tipo: "Ordinaria" },
];

const VOTOS_POSIBLES = ["afirmativo", "negativo", "abstencion", "ausente"];

function seededRandom(seed) {
  let s = seed;
  return () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
}

const LEGISLATORS_SAMPLE = PROVINCES.map((prov, i) => {
  const rnd = seededRandom(i * 37 + 11);
  const camara = i % 3 === 0 ? "Senado" : "Diputados";

  // Asistencia por sesión, con fecha exacta — la asistencia % se deriva de esto
  const sesiones = {};
  SESIONES_EJEMPLO.forEach((s) => {
    sesiones[s.id] = rnd() < 0.78 ? "presente" : "ausente";
  });
  const presentesCount = Object.values(sesiones).filter((v) => v === "presente").length;
  const ausentesCount = SESIONES_EJEMPLO.length - presentesCount;
  const asistencia = Math.round((presentesCount / SESIONES_EJEMPLO.length) * 100);

  const votos = {};
  VOTACIONES_EJEMPLO.forEach((v, vi) => {
    votos[v.id] = VOTOS_POSIBLES[Math.floor(rnd() * (vi === 1 ? 3 : 4))];
  });
  const proyectosCount = Math.floor(rnd() * 4);
  const proyectos = Array.from({ length: proyectosCount }, (_, pi) =>
    ["Régimen de Fomento Local", "Modificación Código Civil", "Declaración de Interés Cultural", "Creación de Registro Único"][pi % 4]
  );
  return {
    id: `l-${prov.id}`,
    nombre: NAMES[i],
    camara,
    provinciaId: prov.id,
    bloque: BLOQUES[i % BLOQUES.length],
    asistencia,
    sesiones,
    presentesCount,
    ausentesCount,
    votos,
    proyectos,
  };
});

// Fuente de datos: intenta cargar /data/legisladores.json (generado por
// export_to_json.py a partir de la base real). Si no existe todavía —por
// ejemplo, en desarrollo antes de correr el ETL— usa los datos de ejemplo,
// y lo deja bien visible en el encabezado para que no se confunda con datos reales.
function useLegislativeData() {
  const [state, setState] = useState({
    loading: true,
    isSample: true,
    legislators: LEGISLATORS_SAMPLE,
    votaciones: VOTACIONES_EJEMPLO,
    sesiones: SESIONES_EJEMPLO,
  });

  React.useEffect(() => {
    let cancelado = false;
    fetch("/data/legisladores.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("sin datos reales"))))
      .then((data) => {
        if (cancelado) return;
        setState({
          loading: false,
          isSample: false,
          legislators: data.legisladores,
          votaciones: data.votaciones,
          sesiones: data.sesiones,
        });
      })
      .catch(() => {
        if (cancelado) return;
        setState((s) => ({ ...s, loading: false }));
      });
    return () => { cancelado = true; };
  }, []);

  return state;
}

function asistenciaColor(pct) {
  if (pct >= 85) return TOKENS.afirmativo;
  if (pct >= 65) return TOKENS.abstencion;
  return TOKENS.negativo;
}

function votoColor(voto) {
  return {
    afirmativo: TOKENS.afirmativo,
    negativo: TOKENS.negativo,
    abstencion: TOKENS.abstencion,
    ausente: TOKENS.ausente,
  }[voto];
}

function votoLabel(voto) {
  return {
    afirmativo: "A favor",
    negativo: "En contra",
    abstencion: "Abstención",
    ausente: "Ausente",
  }[voto];
}

function RingGauge({ pct, size = 64, stroke = 6 }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (pct / 100) * c;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={TOKENS.line} strokeWidth={stroke} />
      <circle
        cx={size / 2} cy={size / 2} r={r} fill="none"
        stroke={asistenciaColor(pct)} strokeWidth={stroke} strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={offset}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: "stroke-dashoffset 0.6s ease" }}
      />
      <text x="50%" y="52%" textAnchor="middle" dominantBaseline="middle"
        fontFamily="'IBM Plex Mono', monospace" fontSize={size * 0.24} fill={TOKENS.textPrimary} fontWeight="600">
        {pct}%
      </text>
    </svg>
  );
}

export default function ControlCiudadano() {
  const [selectedProvince, setSelectedProvince] = useState(null);
  const [selectedLegislator, setSelectedLegislator] = useState(null);
  const { legislators: LEGISLATORS, votaciones: VOTACIONES, sesiones: SESIONES, isSample } = useLegislativeData();

  const provinceLegislators = useMemo(
    () => LEGISLATORS.filter((l) => l.provinciaId === selectedProvince),
    [selectedProvince, LEGISLATORS]
  );

  const maxX = VIEW_W;
  const maxY = VIEW_H;

  return (
    <div style={styles.page}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
        * { box-sizing: border-box; }
        .prov-cell { cursor: pointer; transition: fill-opacity 0.15s ease, filter 0.15s ease; }
        .prov-cell:hover { filter: brightness(1.25); }
        .prov-cell:focus-visible { outline: 2px solid ${TOKENS.gold}; outline-offset: 2px; }
        .leg-card { transition: border-color 0.15s ease, transform 0.15s ease; cursor: pointer; }
        .leg-card:hover { border-color: ${TOKENS.gold}; transform: translateY(-1px); }
        .leg-card:focus-visible { outline: 2px solid ${TOKENS.gold}; }
        @media (prefers-reduced-motion: reduce) {
          .prov-dot, .leg-card, circle { transition: none !important; }
        }
        @media (min-width: 760px) {
          .layout { flex-direction: row !important; }
          .map-col { width: 340px !important; flex-shrink: 0; }
        }
      `}</style>

      {/* Hero */}
      <header style={styles.hero}>
        <div style={styles.eyebrow}>{isSample ? "DATOS DE EJEMPLO — corré el ETL para ver datos reales" : "DATOS OFICIALES"}</div>
        <h1 style={styles.title}>Control Ciudadano</h1>
        <p style={styles.subtitle}>
          Asistencia, votos y proyectos de diputados y senadores nacionales, por provincia.
          Tocá una provincia en el mapa para ver quién la representa.
        </p>
      </header>

      <div className="layout" style={styles.layout}>
        {/* Mapa */}
        <div className="map-col" style={styles.mapCol}>
          <svg viewBox={`0 0 ${maxX} ${maxY}`} style={styles.mapSvg} role="img" aria-label="Mapa de la Argentina con sus provincias">
            {PROVINCES.filter((p) => p.id !== "caba").map((prov) => {
              const shape = PROVINCE_SHAPES[prov.id];
              if (!shape) return null;
              const leg = LEGISLATORS.find((l) => l.provinciaId === prov.id);
              const isSelected = selectedProvince === prov.id;
              const fillColor = leg ? asistenciaColor(leg.asistencia) : TOKENS.line;
              return (
                <path
                  key={prov.id}
                  className="prov-cell"
                  d={shape.path}
                  fill={fillColor}
                  fillOpacity={isSelected ? 0.9 : 0.62}
                  stroke={isSelected ? TOKENS.gold : TOKENS.bgAlt}
                  strokeWidth={isSelected ? 2 : 1}
                  strokeLinejoin="round"
                  tabIndex={0}
                  role="button"
                  aria-label={`${prov.name}${leg ? `, asistencia ${leg.asistencia}%` : ""}`}
                  onClick={() => { setSelectedProvince(prov.id); setSelectedLegislator(null); }}
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { setSelectedProvince(prov.id); setSelectedLegislator(null); } }}
                />
              );
            })}
            {/* CABA no viene delimitada en el mapa fuente: se marca como punto sobre Buenos Aires */}
            {(() => {
              const leg = LEGISLATORS.find((l) => l.provinciaId === "caba");
              const isSelected = selectedProvince === "caba";
              return (
                <circle
                  className="prov-cell"
                  cx={CABA_MARKER.cx} cy={CABA_MARKER.cy}
                  r={isSelected ? 6 : 4.5}
                  fill={leg ? asistenciaColor(leg.asistencia) : TOKENS.line}
                  stroke={isSelected ? TOKENS.gold : TOKENS.bgAlt}
                  strokeWidth={isSelected ? 2 : 1}
                  tabIndex={0}
                  role="button"
                  aria-label={`CABA${leg ? `, asistencia ${leg.asistencia}%` : ""}`}
                  onClick={() => { setSelectedProvince("caba"); setSelectedLegislator(null); }}
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { setSelectedProvince("caba"); setSelectedLegislator(null); } }}
                />
              );
            })()}
          </svg>
          <div style={styles.mapCaption}>Contorno real, extraído de un mapa político — CABA marcada como punto</div>
          <div style={styles.legend}>
            <LegendDot color={TOKENS.afirmativo} label="Asistencia alta" />
            <LegendDot color={TOKENS.abstencion} label="Media" />
            <LegendDot color={TOKENS.negativo} label="Baja" />
          </div>
        </div>

        {/* Panel de contenido */}
        <div style={styles.contentCol}>
          {!selectedProvince && (
            <div style={styles.emptyState}>
              <div style={styles.emptyGlyph}>◎</div>
              <p style={styles.emptyText}>Elegí una provincia en el mapa para ver sus legisladores.</p>
            </div>
          )}

          {selectedProvince && !selectedLegislator && (
            <div>
              <h2 style={styles.provinceTitle}>
                {PROVINCES.find((p) => p.id === selectedProvince)?.name}
              </h2>
              {provinceLegislators.length === 0 && (
                <p style={styles.emptyText}>Sin datos de ejemplo cargados para esta provincia todavía.</p>
              )}
              {provinceLegislators.map((leg) => (
                <div
                  key={leg.id}
                  className="leg-card"
                  style={styles.legCard}
                  tabIndex={0}
                  role="button"
                  onClick={() => setSelectedLegislator(leg.id)}
                  onKeyDown={(e) => { if (e.key === "Enter") setSelectedLegislator(leg.id); }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                    <RingGauge pct={leg.asistencia} size={52} stroke={5} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={styles.legName}>{leg.nombre}</div>
                      <div style={styles.legMeta}>
                        <span style={styles.badge}>{leg.camara}</span>
                        <span style={styles.metaText}>{leg.bloque}</span>
                      </div>
                    </div>
                    <div style={styles.chevron}>›</div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {selectedLegislator && (() => {
            const leg = LEGISLATORS.find((l) => l.id === selectedLegislator);
            // Con datos reales, SESIONES/VOTACIONES son listas globales que mezclan
            // Diputados y Senado (y todo el historial de períodos). Filtramos a solo
            // las sesiones/votaciones donde este legislador tiene un registro real —
            // así no aparece "ausente" en sesiones de la otra cámara, ni en años
            // anteriores a su propio mandato.
            const sesionesDeLegislador = SESIONES.filter((s) => leg.sesiones[s.id] !== undefined);
            const votacionesDeLegislador = VOTACIONES.filter((v) => leg.votos[v.id] !== undefined);
            return (
              <div>
                <button style={styles.backBtn} onClick={() => setSelectedLegislator(null)}>← Volver</button>

                <div style={styles.detailHeader}>
                  <RingGauge pct={leg.asistencia} size={72} stroke={6} />
                  <div>
                    <div style={styles.detailName}>{leg.nombre}</div>
                    <div style={styles.legMeta}>
                      <span style={styles.badge}>{leg.camara}</span>
                      <span style={styles.metaText}>{leg.bloque} · {PROVINCES.find(p => p.id === leg.provinciaId)?.name}</span>
                    </div>
                  </div>
                </div>

                <div style={styles.sectionLabel}>Asistencia a sesiones</div>
                <div style={styles.attendanceSummary}>
                  <SummaryStat value={sesionesDeLegislador.length} label="Sesiones" color={TOKENS.textPrimary} />
                  <SummaryStat value={leg.presentesCount} label="Presente" color={TOKENS.afirmativo} />
                  <SummaryStat value={leg.ausentesCount} label="Ausente" color={TOKENS.negativo} />
                </div>
                <div style={styles.votesList}>
                  {sesionesDeLegislador.map((s) => {
                    const estado = leg.sesiones[s.id];
                    return (
                      <div key={s.id} style={styles.voteRow}>
                        <span style={{ ...styles.voteDot, background: estado === "presente" ? TOKENS.afirmativo : TOKENS.negativo }} />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={styles.voteTitle}>Sesión {(s.tipo || "sin tipo").toLowerCase()}</div>
                          <div style={styles.voteDate}>{s.fecha}</div>
                        </div>
                        <div style={{ ...styles.voteTag, color: estado === "presente" ? TOKENS.afirmativo : TOKENS.negativo }}>
                          {estado === "presente" ? "Presente" : "Ausente"}
                        </div>
                      </div>
                    );
                  })}
                </div>

                <div style={styles.sectionLabel}>Votos recientes</div>
                <div style={styles.votesList}>
                  {votacionesDeLegislador.map((v) => (
                    <div key={v.id} style={styles.voteRow}>
                      <span style={{ ...styles.voteDot, background: votoColor(leg.votos[v.id]) }} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={styles.voteTitle}>{v.titulo}</div>
                        <div style={styles.voteDate}>{v.fecha}</div>
                      </div>
                      <div style={{ ...styles.voteTag, color: votoColor(leg.votos[v.id]) }}>
                        {votoLabel(leg.votos[v.id])}
                      </div>
                    </div>
                  ))}
                </div>

                <div style={styles.sectionLabel}>
                  Proyectos presentados {leg.proyectos.length > 0 ? `(${leg.proyectos.length})` : ""}
                </div>
                {leg.proyectos.length === 0 ? (
                  <p style={styles.emptyText}>Sin proyectos de ejemplo cargados.</p>
                ) : (
                  <ul style={styles.projectList}>
                    {leg.proyectos.map((p, i) => (
                      <li key={i} style={styles.projectItem}>{p}</li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })()}
        </div>
      </div>
    </div>
  );
}

function SummaryStat({ value, label, color }) {
  return (
    <div style={styles.summaryStat}>
      <div style={{ ...styles.summaryValue, color }}>{value}</div>
      <div style={styles.summaryLabel}>{label}</div>
    </div>
  );
}

function LegendDot({ color, label }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: color, display: "inline-block" }} />
      <span style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: 11, color: TOKENS.textMuted }}>{label}</span>
    </div>
  );
}

const styles = {
  page: {
    background: TOKENS.bg,
    color: TOKENS.textPrimary,
    fontFamily: "'IBM Plex Sans', sans-serif",
    minHeight: "100%",
    padding: "20px 16px 40px",
  },
  hero: { marginBottom: 20 },
  eyebrow: {
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: 11,
    letterSpacing: "0.12em",
    color: TOKENS.gold,
    marginBottom: 8,
  },
  title: {
    fontFamily: "'Source Serif 4', serif",
    fontWeight: 700,
    fontSize: 30,
    margin: "0 0 8px",
    color: TOKENS.textPrimary,
  },
  subtitle: {
    fontSize: 14,
    lineHeight: 1.5,
    color: TOKENS.textMuted,
    margin: 0,
    maxWidth: 520,
  },
  layout: { display: "flex", flexDirection: "column", gap: 20 },
  mapCol: { display: "flex", flexDirection: "column", alignItems: "center" },
  mapSvg: {
    width: "100%",
    maxWidth: 320,
    height: "auto",
    background: TOKENS.bgAlt,
    borderRadius: 12,
    border: `1px solid ${TOKENS.line}`,
    padding: 8,
  },
  legend: { display: "flex", gap: 16, marginTop: 12, flexWrap: "wrap", justifyContent: "center" },
  mapCaption: {
    fontSize: 10.5,
    color: TOKENS.textMuted,
    textAlign: "center",
    marginTop: 8,
    maxWidth: 260,
    lineHeight: 1.4,
  },
  contentCol: { flex: 1, minWidth: 0 },
  emptyState: { textAlign: "center", padding: "40px 20px", border: `1px dashed ${TOKENS.line}`, borderRadius: 12 },
  emptyGlyph: { fontSize: 28, color: TOKENS.goldSoft, marginBottom: 10 },
  emptyText: { color: TOKENS.textMuted, fontSize: 13.5, margin: 0 },
  provinceTitle: {
    fontFamily: "'Source Serif 4', serif",
    fontSize: 22,
    fontWeight: 600,
    margin: "0 0 14px",
  },
  legCard: {
    background: TOKENS.surface,
    border: `1px solid ${TOKENS.line}`,
    borderRadius: 10,
    padding: 14,
    marginBottom: 10,
  },
  legName: { fontSize: 15.5, fontWeight: 600, marginBottom: 4 },
  legMeta: { display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" },
  badge: {
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: 10.5,
    color: TOKENS.sky,
    border: `1px solid ${TOKENS.sky}55`,
    borderRadius: 4,
    padding: "1px 6px",
  },
  metaText: { fontSize: 12.5, color: TOKENS.textMuted },
  chevron: { fontSize: 22, color: TOKENS.textMuted },
  backBtn: {
    background: "none",
    border: "none",
    color: TOKENS.sky,
    fontFamily: "'IBM Plex Sans', sans-serif",
    fontSize: 13,
    cursor: "pointer",
    padding: 0,
    marginBottom: 16,
  },
  detailHeader: { display: "flex", alignItems: "center", gap: 16, marginBottom: 24 },
  detailName: { fontFamily: "'Source Serif 4', serif", fontSize: 20, fontWeight: 600, marginBottom: 6 },
  sectionLabel: {
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: 11,
    letterSpacing: "0.08em",
    color: TOKENS.goldSoft,
    textTransform: "uppercase",
    margin: "22px 0 10px",
  },
  attendanceSummary: {
    display: "flex",
    gap: 10,
    marginBottom: 12,
  },
  summaryStat: {
    flex: 1,
    background: TOKENS.surface,
    border: `1px solid ${TOKENS.line}`,
    borderRadius: 8,
    padding: "10px 8px",
    textAlign: "center",
  },
  summaryValue: {
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: 20,
    fontWeight: 600,
  },
  summaryLabel: {
    fontSize: 10.5,
    color: TOKENS.textMuted,
    marginTop: 2,
    textTransform: "uppercase",
    letterSpacing: "0.04em",
  },
  votesList: { display: "flex", flexDirection: "column", gap: 8 },
  voteRow: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    background: TOKENS.surface,
    border: `1px solid ${TOKENS.line}`,
    borderRadius: 8,
    padding: "10px 12px",
  },
  voteDot: { width: 9, height: 9, borderRadius: "50%", flexShrink: 0 },
  voteTitle: { fontSize: 13.5, fontWeight: 500 },
  voteDate: { fontSize: 11.5, color: TOKENS.textMuted, marginTop: 2 },
  voteTag: { fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, whiteSpace: "nowrap" },
  projectList: { margin: 0, padding: "0 0 0 18px", display: "flex", flexDirection: "column", gap: 8 },
  projectItem: { fontSize: 13.5, color: TOKENS.textPrimary, lineHeight: 1.4 },
};
