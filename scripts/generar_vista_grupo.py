import json

with open("/tmp/cartera_laura_consolidada.json", encoding="utf-8") as f:
    data = json.load(f)

n_total = len(data)
n_multi = sum(1 for f in data if f["n_pos"] > 1)
n_ada_rojo = sum(1 for f in data if f["ada_estado"] == "NEGATIVA")
n_ada_amarillo = sum(1 for f in data if f["ada_estado"] == "NEGATIVA_CONTROLADA")
n_ada_verde = sum(1 for f in data if f["ada_estado"] == "POSITIVA")

perdidos_ada = [f for f in data if f["perdido_ada"]]
perdidos_dex = [f for f in data if f["perdido_dex"]]
n_perdidos_ada = len(perdidos_ada)
n_perdidos_dex = len(perdidos_dex)
total_perdido_ada = sum(f["perdida_ada_valor"] for f in perdidos_ada)
total_perdido_dex = sum(f["perdida_dex_valor"] for f in perdidos_dex)

grupos = sorted(set(f["grupo"] for f in data if f["grupo"]))
grupo_counts = {g: sum(1 for f in data if f["grupo"] == g) for g in grupos}
n_sin_grupo = sum(1 for f in data if not f["grupo"])

data_json = json.dumps(data, ensure_ascii=False)

grupo_chips = "\n    ".join(
    f'<button class="chip-btn" data-grupo="{g}">{g} ({grupo_counts[g]})</button>' for g in grupos
)

def fmt_eur(v):
    return f"{v:,.0f} €".replace(",", ".")

perdidos_ada_html = ""
for f in sorted(perdidos_ada, key=lambda x: -x["perdida_ada_valor"]):
    marcas_html = " · ".join(f'{m["marca"]}: {fmt_eur(m["valor"])}' for m in f["perdida_ada_marcas"])
    pos_txt = " + ".join(f["pos_ids"])
    perdidos_ada_html += f"""
      <div class="perdido-row">
        <div class="perdido-head">
          <span class="perdido-nombre">{f["nombre"]}</span>
          <span class="perdido-total">−{fmt_eur(f["perdida_ada_valor"])}/año</span>
        </div>
        <div class="perdido-sub">{f["poblacion"]} · {pos_txt}</div>
        <div class="perdido-marcas">{marcas_html}</div>
      </div>"""

perdidos_dex_html = ""
for f in sorted(perdidos_dex, key=lambda x: -x["perdida_dex_valor"]):
    pos_txt = " + ".join(f["pos_ids"])
    ada_nota = "Pacto ADA sano" if f["ada_estado"] in ("POSITIVA", "NEGATIVA_CONTROLADA") else ("Pacto ADA también en rojo" if f["ada_estado"] == "NEGATIVA" else "")
    perdidos_dex_html += f"""
      <div class="perdido-row">
        <div class="perdido-head">
          <span class="perdido-nombre">{f["nombre"]}</span>
          <span class="perdido-total">−{fmt_eur(f["perdida_dex_valor"])}/año</span>
        </div>
        <div class="perdido-sub">{f["poblacion"]} · {pos_txt} · {ada_nota}</div>
      </div>"""

html = f"""<title>Cartera de Farmacias</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,500&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

:root {{
  --bg: #EEF2F1; --surface: #FFFFFF; --surface-2: #E4EAE9; --ink: #142027; --ink-soft: #4B5C60;
  --border: #CBD7D6; --accent: #0E7C86; --accent-ink: #EAF7F7;
  --ok: #2A7A4E; --ok-bg: #E3F1E7; --ok-border: #BEDCC7;
  --warn: #96691C; --warn-bg: #F5EBD8; --warn-border: #E4CFA0;
  --bad: #A8362F; --bad-bg: #F6E4E1; --bad-border: #E7BFB8;
  --nd: #6B7A7D; --nd-bg: #E9EDEC; --nd-border: #D3DBDA;
  --shadow: 0 1px 2px rgba(20,32,39,0.06), 0 8px 24px -12px rgba(20,32,39,0.18);
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg: #101A1D; --surface: #172226; --surface-2: #1D2A2E; --ink: #E7EEEE; --ink-soft: #A6BABC;
    --border: #2B3D40; --accent: #57D3D9; --accent-ink: #07282A;
    --ok: #5FC98B; --ok-bg: #16302280; --ok-border: #2E5240;
    --warn: #E5AC48; --warn-bg: #3B2E1480; --warn-border: #5C4A26;
    --bad: #E2766D; --bad-bg: #3B201D80; --bad-border: #5C332C;
    --nd: #97A5A7; --nd-bg: #26343680; --nd-border: #3A4B4E;
    --shadow: 0 1px 2px rgba(0,0,0,0.4), 0 8px 24px -12px rgba(0,0,0,0.6);
  }}
}}
:root[data-theme="dark"] {{
  --bg: #101A1D; --surface: #172226; --surface-2: #1D2A2E; --ink: #E7EEEE; --ink-soft: #A6BABC;
  --border: #2B3D40; --accent: #57D3D9; --accent-ink: #07282A;
  --ok: #5FC98B; --ok-bg: #16302280; --ok-border: #2E5240;
  --warn: #E5AC48; --warn-bg: #3B2E1480; --warn-border: #5C4A26;
  --bad: #E2766D; --bad-bg: #3B201D80; --bad-border: #5C332C;
  --nd: #97A5A7; --nd-bg: #26343680; --nd-border: #3A4B4E;
  --shadow: 0 1px 2px rgba(0,0,0,0.4), 0 8px 24px -12px rgba(0,0,0,0.6);
}}

* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{
  background: var(--bg); color: var(--ink);
  font-family: 'IBM Plex Sans', system-ui, -apple-system, sans-serif;
  -webkit-font-smoothing: antialiased; line-height: 1.45;
}}
.page {{ max-width: 1000px; margin: 0 auto; padding: 20px 16px 64px; display: flex; flex-direction: column; gap: 16px; }}

.masthead {{ background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 18px 20px; box-shadow: var(--shadow); }}
.eyebrow {{ font-family: 'IBM Plex Mono', monospace; font-size: 11px; letter-spacing: 0.09em; text-transform: uppercase; color: var(--accent); font-weight: 600; }}
.titulo {{ font-family: 'Newsreader', Georgia, serif; font-weight: 600; font-size: clamp(22px, 4vw, 28px); text-wrap: balance; margin: 2px 0 0; }}
.subt {{ font-size: 13.5px; color: var(--ink-soft); margin-top: 4px; }}

.stats-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; }}
.stat-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px; box-shadow: var(--shadow); }}
.stat-num {{ font-family: 'IBM Plex Mono', monospace; font-size: 22px; font-weight: 600; font-variant-numeric: tabular-nums; }}
.stat-label {{ font-size: 11px; color: var(--ink-soft); text-transform: uppercase; letter-spacing: 0.04em; margin-top: 2px; }}
.stat-card.bad .stat-num {{ color: var(--bad); }}
.stat-card.warn .stat-num {{ color: var(--warn); }}
.stat-card.ok .stat-num {{ color: var(--ok); }}

.controls {{ background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 14px 16px; box-shadow: var(--shadow); display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }}
.chip-btn {{ font-family: 'IBM Plex Mono', monospace; font-size: 12px; padding: 6px 12px; border-radius: 999px; border: 1px solid var(--border); background: var(--surface-2); color: var(--ink-soft); cursor: pointer; }}
.chip-btn.activo {{ background: var(--accent); border-color: var(--accent); color: var(--accent-ink); font-weight: 600; }}
.chip-btn.perdidos.activo {{ background: var(--bad); border-color: var(--bad); color: #fff; }}
input#buscar {{ flex: 1; min-width: 160px; font-family: 'IBM Plex Sans', sans-serif; font-size: 14px; padding: 7px 12px; border-radius: 8px; border: 1px solid var(--border); background: var(--surface-2); color: var(--ink); }}
input#buscar:focus {{ outline: 2px solid var(--accent); outline-offset: 1px; }}
.chip-btn.custom {{ border-style: dashed; }}
.chip-btn .chip-del {{ margin-left: 6px; opacity: 0.55; }}
.chip-btn .chip-del:hover {{ opacity: 1; }}

.seleccion-bar {{ background: var(--accent-ink); border: 1px solid var(--accent); border-radius: 14px; padding: 12px 16px; box-shadow: var(--shadow); display: none; flex-wrap: wrap; gap: 12px 18px; align-items: center; }}
.seleccion-bar.visible {{ display: flex; }}
.seleccion-bar .sel-count {{ font-weight: 600; font-size: 13.5px; white-space: nowrap; }}
.seleccion-bar .sel-resumen {{ font-family: 'IBM Plex Mono', monospace; font-size: 12.5px; color: var(--ink-soft); display: flex; gap: 16px; flex-wrap: wrap; }}
.seleccion-bar .sel-resumen b {{ font-weight: 600; }}
.seleccion-bar .sel-acciones {{ display: flex; gap: 8px; align-items: center; margin-left: auto; flex-wrap: wrap; }}
.seleccion-bar .sel-objetivo-nota {{ width: 100%; font-family: 'IBM Plex Sans', sans-serif; font-size: 11px; color: var(--ink-soft); font-style: italic; }}
.sel-marcas {{ width: 100%; display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 6px 14px; border-top: 1px dashed var(--border); padding-top: 10px; margin-top: 2px; }}
.sel-marca-item {{ font-family: 'IBM Plex Mono', monospace; font-size: 11.5px; color: var(--ink-soft); display: flex; justify-content: space-between; gap: 8px; }}
.sel-marca-item .nombre-marca {{ color: var(--ink); font-weight: 500; }}
.seleccion-bar input#nombre-grupo {{ font-family: 'IBM Plex Sans', sans-serif; font-size: 13px; padding: 6px 10px; border-radius: 8px; border: 1px solid var(--border); background: var(--surface); color: var(--ink); width: 160px; }}
.seleccion-bar button {{ font-family: 'IBM Plex Mono', monospace; font-size: 11.5px; padding: 6px 12px; border-radius: 8px; border: 1px solid var(--accent); background: var(--accent); color: var(--accent-ink); cursor: pointer; font-weight: 600; }}
.seleccion-bar button.secundario {{ background: transparent; color: var(--accent); }}
th.check-th, td.check-cell {{ width: 26px; padding-left: 12px; padding-right: 0; }}

.tabla-panel {{ background: var(--surface); border: 1px solid var(--border); border-radius: 14px; box-shadow: var(--shadow); overflow-x: auto; }}
table.cartera {{ width: 100%; border-collapse: collapse; min-width: 720px; }}
table.cartera th {{ text-align: left; font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--ink-soft); font-weight: 600; padding: 10px 12px; font-family: 'IBM Plex Mono', monospace; cursor: pointer; border-bottom: 1px solid var(--border); white-space: nowrap; position: sticky; top: 0; background: var(--surface); }}
table.cartera th.num, table.cartera td.num {{ text-align: right; }}
table.cartera th:hover {{ color: var(--accent); }}
.sort-alt {{ color: var(--accent); text-decoration: underline; text-decoration-style: dotted; margin-left: 2px; }}
.sort-alt:hover {{ color: var(--ink); }}
table.cartera td {{ padding: 9px 12px; border-bottom: 1px solid var(--border); font-size: 13px; vertical-align: middle; }}
table.cartera tbody tr:hover {{ background: var(--surface-2); }}
table.cartera tbody tr.fila-perdida {{ background: var(--bad-bg); }}
.nombre-cell {{ font-weight: 500; }}
.n-pos-badge {{ font-family: 'IBM Plex Mono', monospace; font-size: 9.5px; color: var(--accent); background: var(--accent-ink); border: 1px solid var(--accent); border-radius: 4px; padding: 0 4px; margin-left: 6px; }}
.pobl-cell {{ color: var(--ink-soft); font-size: 11.5px; }}
.grupo-tag {{ font-family: 'IBM Plex Mono', monospace; font-size: 10px; padding: 2px 7px; border-radius: 5px; background: var(--surface-2); color: var(--ink-soft); border: 1px solid var(--border); }}
.estado-cell {{ font-family: 'IBM Plex Mono', monospace; font-variant-numeric: tabular-nums; text-align: right; white-space: nowrap; }}
.importes-line {{ font-size: 11px; color: var(--ink-soft); margin-bottom: 2px; }}
.estado-cell .evol {{ font-weight: 600; }}
.evol.pos {{ color: var(--ok); }} .evol.neg-c {{ color: var(--warn); }} .evol.neg {{ color: var(--bad); }} .evol.nd {{ color: var(--nd); }}

.section-title {{ font-family: 'Newsreader', Georgia, serif; font-size: 16px; font-weight: 600; font-style: italic; color: var(--ink-soft); margin: 4px 2px 0; }}
.perdidos-panel {{ background: var(--surface); border: 1px solid var(--bad-border); border-radius: 14px; padding: 16px 18px; box-shadow: var(--shadow); display: flex; flex-direction: column; gap: 12px; }}
.perdidos-intro {{ font-size: 13px; color: var(--ink-soft); }}
.perdido-row {{ border-top: 1px solid var(--border); padding-top: 10px; }}
.perdido-row:first-of-type {{ border-top: none; padding-top: 0; }}
.perdido-head {{ display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }}
.perdido-nombre {{ font-weight: 600; font-size: 14px; }}
.perdido-total {{ font-family: 'IBM Plex Mono', monospace; font-weight: 600; color: var(--bad); font-variant-numeric: tabular-nums; white-space: nowrap; }}
.perdido-sub {{ font-size: 11.5px; color: var(--ink-soft); margin-top: 1px; }}
.perdido-marcas {{ font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: var(--ink-soft); margin-top: 4px; }}

.footer-note {{ font-size: 11.5px; color: var(--ink-soft); text-align: center; padding: 4px 12px 0; font-family: 'IBM Plex Mono', monospace; line-height: 1.6; }}

table.cartera tbody tr {{ cursor: pointer; }}

.ficha-overlay {{ position: fixed; inset: 0; background: rgba(10,16,19,0.55); display: none; align-items: flex-start; justify-content: center; padding: 24px 14px; overflow-y: auto; z-index: 50; }}
.ficha-overlay.visible {{ display: flex; }}
.ficha-modal {{ background: var(--surface); border: 1px solid var(--border); border-radius: 16px; box-shadow: var(--shadow); max-width: 640px; width: 100%; padding: 22px 22px 24px; display: flex; flex-direction: column; gap: 16px; margin: auto 0; }}
.ficha-head {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }}
.ficha-titulo {{ font-family: 'Newsreader', Georgia, serif; font-weight: 600; font-size: 21px; margin: 0; }}
.ficha-sub {{ font-size: 12.5px; color: var(--ink-soft); margin-top: 3px; }}
.ficha-cerrar {{ font-family: 'IBM Plex Mono', monospace; font-size: 13px; background: var(--surface-2); border: 1px solid var(--border); color: var(--ink-soft); border-radius: 8px; width: 30px; height: 30px; cursor: pointer; flex-shrink: 0; }}
.ficha-cerrar:hover {{ color: var(--ink); }}
.ficha-badges {{ display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px; }}
.ficha-badge {{ font-family: 'IBM Plex Mono', monospace; font-size: 10px; padding: 2px 7px; border-radius: 5px; background: var(--surface-2); color: var(--ink-soft); border: 1px solid var(--border); }}
.ficha-pactos {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
@media (max-width: 480px) {{ .ficha-pactos {{ grid-template-columns: 1fr; }} }}
.ficha-pacto-card {{ border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px; display: flex; flex-direction: column; gap: 6px; }}
.ficha-pacto-nombre {{ font-family: 'IBM Plex Mono', monospace; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--ink-soft); font-weight: 600; }}
.ficha-pacto-evol {{ font-family: 'IBM Plex Mono', monospace; font-size: 15px; }}
.ficha-pacto-importes {{ font-size: 11.5px; color: var(--ink-soft); }}
.ficha-pacto-objetivo {{ font-size: 11.5px; color: var(--ink-soft); border-top: 1px dashed var(--border); padding-top: 6px; margin-top: 2px; }}
.ficha-pacto-objetivo b {{ color: var(--ink); font-family: 'IBM Plex Mono', monospace; }}
.ficha-marcas-tabla {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
.ficha-marcas-tabla th {{ text-align: left; font-size: 10px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--ink-soft); font-weight: 600; padding: 6px 8px; border-bottom: 1px solid var(--border); font-family: 'IBM Plex Mono', monospace; }}
.ficha-marcas-tabla td {{ padding: 6px 8px; border-bottom: 1px solid var(--border); font-family: 'IBM Plex Mono', monospace; }}
.ficha-marcas-tabla td.nombre-marca-cell {{ font-family: 'IBM Plex Sans', sans-serif; }}
.ficha-marcas-tabla th.num, .ficha-marcas-tabla td.num {{ text-align: right; }}
.ficha-perdida {{ background: var(--bad-bg); border: 1px solid var(--bad-border); border-radius: 10px; padding: 10px 12px; font-size: 12.5px; color: var(--bad); }}
.ficha-veeva-ok {{ background: var(--ok-bg); border: 1px solid var(--ok-border); border-radius: 10px; padding: 10px 12px; font-size: 12.5px; }}
.ficha-veeva-nd {{ background: var(--nd-bg); border: 1px solid var(--nd-border); border-radius: 10px; padding: 10px 12px; font-size: 12.5px; color: var(--ink-soft); }}

@media (max-width: 620px) {{ .pobl-cell {{ display: none; }} }}
</style>

<div class="page">
  <div class="masthead">
    <span class="eyebrow">Vista de grupo · Cartera</span>
    <h1 class="titulo">Laura Luquin Franquet — {n_total} farmacias reales</h1>
    <div class="subt">Consolidado por identidad física (dirección+CP+población) — {n_multi} de estas farmacias tenían 2+ POS-Id que se han sumado. Evolución YTD vs. año anterior, LOB corte 03/08/2026.</div>
  </div>

  <div class="stats-row">
    <div class="stat-card bad"><div class="stat-num">{n_ada_rojo}</div><div class="stat-label">ADA en rojo</div></div>
    <div class="stat-card warn"><div class="stat-num">{n_ada_amarillo}</div><div class="stat-label">ADA controlado</div></div>
    <div class="stat-card ok"><div class="stat-num">{n_ada_verde}</div><div class="stat-label">ADA positivo</div></div>
    <div class="stat-card bad"><div class="stat-num">{n_perdidos_ada}</div><div class="stat-label">ADA perdido (0€ real)</div></div>
    <div class="stat-card bad"><div class="stat-num">{n_perdidos_dex}</div><div class="stat-label">Dexeryl perdido</div></div>
  </div>

  <div class="controls">
    <button class="chip-btn activo" data-grupo="todos">Todos ({n_total})</button>
    {grupo_chips}
    <button class="chip-btn" data-grupo="sin">Sin grupo ({n_sin_grupo})</button>
    <span id="custom-grupo-chips"></span>
    <button class="chip-btn" data-filtro="rojo-ada">🔴 Solo ADA en rojo</button>
    <button class="chip-btn perdidos" data-filtro="perdidos">⚫ Solo ADA perdido</button>
    <input id="buscar" type="text" placeholder="Buscar cliente o población…">
  </div>

  <div class="seleccion-bar" id="seleccion-bar">
    <span class="sel-count" id="sel-count">0 seleccionadas</span>
    <div class="sel-resumen" id="sel-resumen"></div>
    <div class="sel-acciones">
      <input id="nombre-grupo" type="text" placeholder="Nombre del grupo…">
      <button id="btn-guardar-grupo">Guardar como grupo</button>
      <button class="secundario" id="btn-limpiar-sel">Limpiar selección</button>
    </div>
    <div class="sel-objetivo-nota" id="sel-objetivo-nota"></div>
    <div class="sel-marcas" id="sel-marcas"></div>
  </div>

  <div class="tabla-panel">
    <table class="cartera" id="tabla">
      <thead>
        <tr>
          <th class="check-th"><input type="checkbox" id="check-all" title="Seleccionar todos los visibles"></th>
          <th data-sort="nombre">Cliente</th>
          <th data-sort="grupo">Grupo</th>
          <th class="num" data-sort="ada_evol">Pacto ADA · 2025→2026 <span class="sort-alt" data-sort="ada_ytd" title="Ordenar por importe">[€]</span></th>
          <th class="num" data-sort="dex_evol">Pacto Dexeryl · 2025→2026 <span class="sort-alt" data-sort="dex_ytd" title="Ordenar por importe">[€]</span></th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>

  <div class="section-title">⚫ Pacto ADA perdido — 0 € reales, qué facturaban y en qué marca</div>
  <div class="perdidos-panel">
    <div class="perdidos-intro">0 € reales este año en TODO el Pacto ADA (no N/D), con facturación real el año pasado. Total en riesgo: <strong style="color:var(--bad)">−{fmt_eur(total_perdido_ada)}/año</strong>.</div>
    {perdidos_ada_html or '<div class="perdidos-intro">Ninguno en tu cartera ahora mismo.</div>'}
  </div>

  <div class="section-title">⚫ Dexeryl perdido — independiente del Pacto ADA</div>
  <div class="perdidos-panel">
    <div class="perdidos-intro">Ojo: estos clientes NO son "clientes perdidos" en general — muchos tienen el Pacto ADA sano, solo han dejado Dexeryl. Total en riesgo: <strong style="color:var(--bad)">−{fmt_eur(total_perdido_dex)}/año</strong>.</div>
    {perdidos_dex_html or '<div class="perdidos-intro">Ninguno en tu cartera ahora mismo.</div>'}
  </div>

  <div class="footer-note">
    Objetivo real de pacto: sale del Listado de Acuerdos Comerciales (solo cuando hay acuerdo Activo) — nunca se inventa. Evolución vs. año anterior siempre disponible desde el LOB.<br>
    🟢 evolución ≥ 0% · 🟡 entre 0% y −15% · 🔴 por debajo de −15% · ⚪ sin datos suficientes en el LOB · Pacto ADA y Pacto Dexeryl nunca se mezclan<br>
    Toca una farmacia en la tabla para abrir su ficha de visita.
  </div>
</div>

<div class="ficha-overlay" id="ficha-overlay">
  <div class="ficha-modal" id="ficha-modal"></div>
</div>

<script>
const DATA = {data_json};

function estadoInfo(estado, evol) {{
  if (estado === 'SIN_DATOS' || evol === null) return {{cls: 'nd', txt: 'N/D'}};
  const txt = (evol >= 0 ? '+' : '') + evol.toFixed(1).replace('.', ',') + ' %';
  if (estado === 'POSITIVA') return {{cls: 'pos', txt}};
  if (estado === 'NEGATIVA_CONTROLADA') return {{cls: 'neg-c', txt}};
  return {{cls: 'neg', txt}};
}}
function semaforo(estado) {{
  return {{POSITIVA: '🟢', NEGATIVA_CONTROLADA: '🟡', NEGATIVA: '🔴', SIN_DATOS: '⚪'}}[estado] || '⚪';
}}

let grupoActivo = 'todos';
let grupoCustomActivo = null;
let soloRojoAda = false;
let soloPerdidosAda = false;
let sortKey = 'ada_evol';
let sortAsc = true;
let selectedIds = new Set();
let filasActuales = [];

let customGrupos = {{}};
try {{
  customGrupos = JSON.parse(localStorage.getItem('vgCustomGrupos') || '{{}}');
}} catch (e) {{ customGrupos = {{}}; }}

function guardaCustomGrupos() {{
  try {{ localStorage.setItem('vgCustomGrupos', JSON.stringify(customGrupos)); }} catch (e) {{}}
}}

function renderCustomChips() {{
  const cont = document.getElementById('custom-grupo-chips');
  cont.innerHTML = Object.keys(customGrupos).map(nombre => {{
    const n = customGrupos[nombre].length;
    return `<button class="chip-btn custom ${{grupoCustomActivo === nombre ? 'activo' : ''}}" data-custom="${{nombre}}">${{nombre}} (${{n}})<span class="chip-del" data-del="${{nombre}}" title="Eliminar grupo">✕</span></button>`;
  }}).join(' ');
  cont.querySelectorAll('.chip-btn[data-custom]').forEach(btn => {{
    btn.addEventListener('click', (ev) => {{
      if (ev.target.dataset.del) return;
      const nombre = btn.dataset.custom;
      document.querySelectorAll('.chip-btn[data-grupo]').forEach(b => b.classList.remove('activo'));
      if (grupoCustomActivo === nombre) {{
        grupoCustomActivo = null;
        document.querySelector('.chip-btn[data-grupo="todos"]').classList.add('activo');
        grupoActivo = 'todos';
      }} else {{
        grupoCustomActivo = nombre;
      }}
      renderCustomChips();
      aplicaFiltros();
    }});
  }});
  cont.querySelectorAll('.chip-del[data-del]').forEach(span => {{
    span.addEventListener('click', (ev) => {{
      ev.stopPropagation();
      const nombre = span.dataset.del;
      delete customGrupos[nombre];
      guardaCustomGrupos();
      if (grupoCustomActivo === nombre) {{ grupoCustomActivo = null; }}
      renderCustomChips();
      aplicaFiltros();
    }});
  }});
}}

function combinaPacto(rows, prefijo) {{
  const ytdVals = rows.map(f => f[prefijo + '_ytd']).filter(v => v !== null && v !== undefined);
  const ytd1Vals = rows.map(f => f[prefijo + '_ytd1']).filter(v => v !== null && v !== undefined);
  if (ytdVals.length === 0 && ytd1Vals.length === 0) return {{ytd: null, ytd1: null, evol: null, estado: 'SIN_DATOS'}};
  const ytd = ytdVals.reduce((a, b) => a + b, 0);
  const ytd1 = ytd1Vals.reduce((a, b) => a + b, 0);
  let evol = null;
  if (ytd1 === 0) {{ evol = ytd === 0 ? null : 100.0; }} else {{ evol = (ytd - ytd1) / ytd1 * 100; }}
  let estado = 'SIN_DATOS';
  if (evol !== null) {{ estado = evol >= 0 ? 'POSITIVA' : (evol >= -15 ? 'NEGATIVA_CONTROLADA' : 'NEGATIVA'); }}
  return {{ytd, ytd1, evol, estado}};
}}

const MARCAS_ORDEN = [
  ['avene_sin_solar', 'Avène (sin solar)'],
  ['avene_solar', 'Avène Solar'],
  ['ducray', 'Ducray'],
  ['aderma', 'A-Derma'],
  ['dexeryl', 'Dexeryl'],
];

function combinaMarca(rows, marcaKey) {{
  const ytdVals = rows.map(f => f.marcas && f.marcas[marcaKey] ? f.marcas[marcaKey].ytd : null).filter(v => v !== null && v !== undefined);
  const ytd1Vals = rows.map(f => f.marcas && f.marcas[marcaKey] ? f.marcas[marcaKey].ytd1 : null).filter(v => v !== null && v !== undefined);
  if (ytdVals.length === 0 && ytd1Vals.length === 0) return {{ytd: null, ytd1: null, evol: null, estado: 'SIN_DATOS'}};
  const ytd = ytdVals.reduce((a, b) => a + b, 0);
  const ytd1 = ytd1Vals.reduce((a, b) => a + b, 0);
  let evol = null;
  if (ytd1 === 0) {{ evol = ytd === 0 ? null : 100.0; }} else {{ evol = (ytd - ytd1) / ytd1 * 100; }}
  let estado = 'SIN_DATOS';
  if (evol !== null) {{ estado = evol >= 0 ? 'POSITIVA' : (evol >= -15 ? 'NEGATIVA_CONTROLADA' : 'NEGATIVA'); }}
  return {{ytd, ytd1, evol, estado}};
}}

function actualizaSeleccionBar() {{
  const bar = document.getElementById('seleccion-bar');
  const seleccionadas = DATA.filter(f => selectedIds.has(f.id));
  if (seleccionadas.length === 0) {{
    bar.classList.remove('visible');
    return;
  }}
  bar.classList.add('visible');
  document.getElementById('sel-count').textContent = seleccionadas.length + ' seleccionadas';
  const ada = combinaPacto(seleccionadas, 'ada');
  const dex = combinaPacto(seleccionadas, 'dex');
  const adaInfo = estadoInfo(ada.estado, ada.evol);
  const dexInfo = estadoInfo(dex.estado, dex.evol);
  document.getElementById('sel-resumen').innerHTML =
    `<span>Pacto ADA: ${{fmtEur(ada.ytd1)}} → ${{fmtEur(ada.ytd)}} <b class="evol ${{adaInfo.cls}}">${{adaInfo.txt}}</b></span>` +
    `<span>Pacto Dexeryl: ${{fmtEur(dex.ytd1)}} → ${{fmtEur(dex.ytd)}} <b class="evol ${{dexInfo.cls}}">${{dexInfo.txt}}</b></span>`;

  const conObjAda = seleccionadas.filter(f => f.ada_objetivo !== null);
  const conObjDex = seleccionadas.filter(f => f.dex_objetivo !== null);
  const notaPartes = [];
  if (conObjAda.length > 0) {{
    const objAda = conObjAda.reduce((a, f) => a + f.ada_objetivo, 0);
    const ytdAda = conObjAda.reduce((a, f) => a + (f.ada_ytd || 0), 0);
    const gapAda = objAda - ytdAda;
    const pctAda = objAda > 0 ? (ytdAda / objAda * 100) : null;
    notaPartes.push(`Pacto ADA vs. objetivo (acuerdo Activo, ${{conObjAda.length}}/${{seleccionadas.length}} farmacias): objetivo ${{fmtEur(objAda)}}, cumplimiento ${{pctAda !== null ? pctAda.toFixed(1).replace('.', ',') + '%' : '—'}}, gap ${{fmtEur(gapAda)}}.`);
  }} else {{
    notaPartes.push('Pacto ADA: ninguna de las farmacias seleccionadas tiene acuerdo comercial Activo con objetivo vigente.');
  }}
  if (conObjDex.length > 0) {{
    const objDex = conObjDex.reduce((a, f) => a + f.dex_objetivo, 0);
    const ytdDex = conObjDex.reduce((a, f) => a + (f.dex_ytd || 0), 0);
    const gapDex = objDex - ytdDex;
    const pctDex = objDex > 0 ? (ytdDex / objDex * 100) : null;
    notaPartes.push(`Pacto Dexeryl vs. objetivo (${{conObjDex.length}}/${{seleccionadas.length}}): objetivo ${{fmtEur(objDex)}}, cumplimiento ${{pctDex !== null ? pctDex.toFixed(1).replace('.', ',') + '%' : '—'}}, gap ${{fmtEur(gapDex)}}.`);
  }} else {{
    notaPartes.push('Pacto Dexeryl: ninguna con acuerdo Activo.');
  }}
  document.getElementById('sel-objetivo-nota').textContent = notaPartes.join(' ') +
    ' El objetivo sale del Listado de Acuerdos Comerciales (CIFRA PACTADA real) — las farmacias sin acuerdo Activo no suman aquí, nunca se inventa un objetivo.';

  document.getElementById('sel-marcas').innerHTML = MARCAS_ORDEN.map(([key, label]) => {{
    const m = combinaMarca(seleccionadas, key);
    const info = estadoInfo(m.estado, m.evol);
    return `<div class="sel-marca-item"><span class="nombre-marca">${{label}}</span><span>${{fmtEur(m.ytd1)}} → ${{fmtEur(m.ytd)}} <b class="evol ${{info.cls}}">${{info.txt}}</b></span></div>`;
  }}).join('');
}}

function aplicaFiltros() {{
  const q = document.getElementById('buscar').value.trim().toLowerCase();
  let filas = DATA.filter(f => {{
    if (grupoCustomActivo) {{
      if (!customGrupos[grupoCustomActivo] || !customGrupos[grupoCustomActivo].includes(f.id)) return false;
    }} else if (grupoActivo !== 'todos') {{
      if (grupoActivo === 'sin' && f.grupo !== null) return false;
      if (grupoActivo !== 'sin' && f.grupo !== grupoActivo) return false;
    }}
    if (soloRojoAda && f.ada_estado !== 'NEGATIVA') return false;
    if (soloPerdidosAda && !f.perdido_ada) return false;
    if (q && !f.nombre.toLowerCase().includes(q) && !f.poblacion.toLowerCase().includes(q)) return false;
    return true;
  }});
  filas.sort((a, b) => {{
    let va = a[sortKey], vb = b[sortKey];
    if (va === null) va = sortKey.includes('evol') ? 999 : '';
    if (vb === null) vb = sortKey.includes('evol') ? 999 : '';
    if (typeof va === 'string') return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
    return sortAsc ? va - vb : vb - va;
  }});
  filasActuales = filas;
  render(filas);
  actualizaSeleccionBar();
}}

function fmtEur(v) {{
  if (v === null || v === undefined) return '—';
  return Math.round(v).toLocaleString('es-ES') + ' €';
}}

function render(filas) {{
  const tbody = document.getElementById('tbody');
  tbody.innerHTML = filas.map(f => {{
    const ada = estadoInfo(f.ada_estado, f.ada_evol);
    const dex = estadoInfo(f.dex_estado, f.dex_evol);
    const badge = f.n_pos > 1 ? `<span class="n-pos-badge">${{f.n_pos}} POS</span>` : '';
    return `<tr class="${{f.perdido_ada ? 'fila-perdida' : ''}}" data-id="${{f.id}}">
      <td class="check-cell"><input type="checkbox" class="row-check" data-id="${{f.id}}" ${{selectedIds.has(f.id) ? 'checked' : ''}}></td>
      <td><div class="nombre-cell">${{f.nombre}}${{badge}}</div><div class="pobl-cell">${{f.poblacion}} · ${{f.pos_ids.join('+')}}</div></td>
      <td>${{f.grupo ? `<span class="grupo-tag">${{f.grupo}}</span>` : ''}}</td>
      <td class="estado-cell">
        <div class="importes-line">${{fmtEur(f.ada_ytd1)}} → ${{fmtEur(f.ada_ytd)}}</div>
        <div>${{semaforo(f.ada_estado)}} <span class="evol ${{ada.cls}}">${{ada.txt}}</span></div>
      </td>
      <td class="estado-cell">
        <div class="importes-line">${{fmtEur(f.dex_ytd1)}} → ${{fmtEur(f.dex_ytd)}}</div>
        <div>${{semaforo(f.dex_estado)}} <span class="evol ${{dex.cls}}">${{dex.txt}}</span></div>
      </td>
    </tr>`;
  }}).join('');
  const checkAll = document.getElementById('check-all');
  if (filas.length > 0 && filas.every(f => selectedIds.has(f.id))) {{
    checkAll.checked = true; checkAll.indeterminate = false;
  }} else if (filas.some(f => selectedIds.has(f.id))) {{
    checkAll.checked = false; checkAll.indeterminate = true;
  }} else {{
    checkAll.checked = false; checkAll.indeterminate = false;
  }}
}}

const MARCA_COMERCIAL_LABEL = {{AVENE: 'Avène (sin solar)', DUCRAY: 'Ducray', 'A-DERMA': 'A-Derma', DEXERYL: 'Dexeryl'}};

function evolucionSimple(ytd, ytd1) {{
  if (ytd === null || ytd === undefined || ytd1 === null || ytd1 === undefined) return {{estado: 'SIN_DATOS', evol: null}};
  let evol;
  if (ytd1 === 0) {{ evol = ytd === 0 ? null : 100.0; }} else {{ evol = (ytd - ytd1) / ytd1 * 100; }}
  let estado = 'SIN_DATOS';
  if (evol !== null) {{ estado = evol >= 0 ? 'POSITIVA' : (evol >= -15 ? 'NEGATIVA_CONTROLADA' : 'NEGATIVA'); }}
  return {{estado, evol}};
}}

function pactoCardHtml(nombre, ytd, ytd1, evol, estado, objetivo, pctCumplimiento, gap) {{
  const info = estadoInfo(estado, evol);
  const objetivoHtml = (objetivo !== null && objetivo !== undefined)
    ? `Objetivo (acuerdo Activo): <b>${{fmtEur(objetivo)}}</b> · cumplimiento <b>${{pctCumplimiento !== null ? pctCumplimiento.toFixed(1).replace('.', ',') + '%' : '—'}}</b> · gap <b>${{fmtEur(gap)}}</b>`
    : 'Objetivo de pacto individual no disponible (sin acuerdo Activo vigente).';
  return `<div class="ficha-pacto-card">
    <div class="ficha-pacto-nombre">${{nombre}}</div>
    <div class="ficha-pacto-importes">${{fmtEur(ytd1)}} → ${{fmtEur(ytd)}}</div>
    <div class="ficha-pacto-evol">${{semaforo(estado)}} <span class="evol ${{info.cls}}">${{info.txt}}</span></div>
    <div class="ficha-pacto-objetivo">${{objetivoHtml}}</div>
  </div>`;
}}

function renderFicha(f) {{
  const posTxt = f.pos_ids.join(' + ');
  const badges = [];
  if (f.n_pos > 1) badges.push(`${{f.n_pos}} POS-Id consolidados`);
  if (f.grupo) badges.push('Grupo ' + f.grupo);
  badges.push(f.tiene_veeva ? '✅ Con captura Veeva' : '⚪ Sin captura Veeva');

  const marcasFilas = MARCAS_ORDEN.map(([key, label]) => {{
    const m = f.marcas[key];
    const {{estado, evol}} = evolucionSimple(m.ytd, m.ytd1);
    const info = estadoInfo(estado, evol);
    return `<tr><td class="nombre-marca-cell">${{label}}</td><td class="num">${{fmtEur(m.ytd1)}}</td><td class="num">${{fmtEur(m.ytd)}}</td><td class="num"><span class="evol ${{info.cls}}">${{info.txt}}</span></td></tr>`;
  }}).join('');

  const objetivoMarcasFilas = Object.keys(MARCA_COMERCIAL_LABEL).map(key => {{
    const obj = f.objetivo_por_marca[key];
    return `<div class="sel-marca-item"><span class="nombre-marca">${{MARCA_COMERCIAL_LABEL[key]}}</span><span>${{obj !== null ? 'objetivo ' + fmtEur(obj) : 'sin acuerdo Activo'}}</span></div>`;
  }}).join('');

  let perdidaHtml = '';
  if (f.perdido_ada) {{
    const marcasTxt = f.perdida_ada_marcas.map(m => `${{m.marca}}: ${{fmtEur(m.valor)}}`).join(' · ');
    perdidaHtml += `<div class="ficha-perdida">⚫ Pacto ADA perdido: 0€ reales este año, facturaba ${{fmtEur(f.perdida_ada_valor)}}/año. ${{marcasTxt}}</div>`;
  }}
  if (f.perdido_dex) {{
    perdidaHtml += `<div class="ficha-perdida">⚫ Dexeryl perdido: 0€ reales este año, facturaba ${{fmtEur(f.perdida_dex_valor)}}/año.</div>`;
  }}

  const veevaHtml = f.tiene_veeva
    ? `<div class="ficha-veeva-ok">✅ Hay captura real de Veeva para este cliente — consulta la ficha completa de visita (con oportunidades por gama y propuesta de pedido) publicada aparte.</div>`
    : `<div class="ficha-veeva-nd">⚪ Sin captura de Veeva para este cliente — no se pueden calcular oportunidades reales por gama (una gama solo es oportunidad si YTD y TAM12M en Veeva son 0 real; sin Veeva no se infiere). Para verlas aquí, hace falta capturar el histórico de pedidos de esta farmacia en Veeva.</div>`;

  document.getElementById('ficha-modal').innerHTML = `
    <div class="ficha-head">
      <div>
        <h2 class="ficha-titulo">${{f.nombre}}</h2>
        <div class="ficha-sub">${{f.direccion}}, ${{f.poblacion}} (${{f.provincia}}) · ${{posTxt}}</div>
        <div class="ficha-badges">${{badges.map(b => `<span class="ficha-badge">${{b}}</span>`).join('')}}</div>
      </div>
      <button class="ficha-cerrar" id="ficha-cerrar-btn" title="Cerrar">✕</button>
    </div>
    <div class="ficha-pactos">
      ${{pactoCardHtml('Pacto ADA', f.ada_ytd, f.ada_ytd1, f.ada_evol, f.ada_estado, f.ada_objetivo, f.ada_pct_cumplimiento, f.ada_gap)}}
      ${{pactoCardHtml('Pacto Dexeryl', f.dex_ytd, f.dex_ytd1, f.dex_evol, f.dex_estado, f.dex_objetivo, f.dex_pct_cumplimiento, f.dex_gap)}}
    </div>
    ${{perdidaHtml}}
    <div>
      <div class="ficha-pacto-nombre" style="margin-bottom:6px;">Desglose por marca (LOB)</div>
      <table class="ficha-marcas-tabla">
        <thead><tr><th>Marca</th><th class="num">2025 (YTD-1)</th><th class="num">2026 (YTD)</th><th class="num">Evolución</th></tr></thead>
        <tbody>${{marcasFilas}}</tbody>
      </table>
    </div>
    <div>
      <div class="ficha-pacto-nombre" style="margin-bottom:6px;">Objetivo pactado por marca comercial</div>
      <div class="sel-marcas" style="border-top:none; padding-top:0;">${{objetivoMarcasFilas}}</div>
    </div>
    ${{veevaHtml}}
  `;
}}

function abreFicha(id) {{
  const f = DATA.find(d => d.id === id);
  if (!f) return;
  renderFicha(f);
  document.getElementById('ficha-overlay').classList.add('visible');
}}
function cierraFicha() {{
  document.getElementById('ficha-overlay').classList.remove('visible');
}}
document.getElementById('ficha-overlay').addEventListener('click', (ev) => {{
  if (ev.target.id === 'ficha-overlay') cierraFicha();
}});
document.getElementById('ficha-modal').addEventListener('click', (ev) => {{
  if (ev.target.id === 'ficha-cerrar-btn') cierraFicha();
}});
document.addEventListener('keydown', (ev) => {{
  if (ev.key === 'Escape') cierraFicha();
}});
document.getElementById('tbody').addEventListener('click', (ev) => {{
  if (ev.target.closest('.check-cell')) return;
  const tr = ev.target.closest('tr[data-id]');
  if (tr) abreFicha(Number(tr.dataset.id));
}});

document.querySelectorAll('.chip-btn[data-grupo]').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('.chip-btn[data-grupo]').forEach(b => b.classList.remove('activo'));
    btn.classList.add('activo');
    grupoActivo = btn.dataset.grupo;
    grupoCustomActivo = null;
    renderCustomChips();
    aplicaFiltros();
  }});
}});
document.getElementById('tbody').addEventListener('change', (ev) => {{
  if (ev.target.classList.contains('row-check')) {{
    const id = Number(ev.target.dataset.id);
    if (ev.target.checked) selectedIds.add(id); else selectedIds.delete(id);
    actualizaSeleccionBar();
  }}
}});
document.getElementById('check-all').addEventListener('change', (ev) => {{
  if (ev.target.checked) {{
    filasActuales.forEach(f => selectedIds.add(f.id));
  }} else {{
    filasActuales.forEach(f => selectedIds.delete(f.id));
  }}
  render(filasActuales);
  actualizaSeleccionBar();
}});
document.getElementById('btn-guardar-grupo').addEventListener('click', () => {{
  const nombre = document.getElementById('nombre-grupo').value.trim();
  if (!nombre) {{ alert('Ponle un nombre al grupo antes de guardarlo.'); return; }}
  customGrupos[nombre] = Array.from(selectedIds);
  guardaCustomGrupos();
  document.getElementById('nombre-grupo').value = '';
  renderCustomChips();
}});
document.getElementById('btn-limpiar-sel').addEventListener('click', () => {{
  selectedIds.clear();
  render(filasActuales);
  actualizaSeleccionBar();
}});
document.querySelector('.chip-btn[data-filtro="rojo-ada"]').addEventListener('click', function() {{
  soloRojoAda = !soloRojoAda;
  this.classList.toggle('activo', soloRojoAda);
  aplicaFiltros();
}});
document.querySelector('.chip-btn[data-filtro="perdidos"]').addEventListener('click', function() {{
  soloPerdidosAda = !soloPerdidosAda;
  this.classList.toggle('activo', soloPerdidosAda);
  aplicaFiltros();
}});
document.getElementById('buscar').addEventListener('input', aplicaFiltros);
document.querySelectorAll('.sort-alt[data-sort]').forEach(span => {{
  span.addEventListener('click', (ev) => {{
    ev.stopPropagation();
    const key = span.dataset.sort;
    if (sortKey === key) sortAsc = !sortAsc; else {{ sortKey = key; sortAsc = false; }}
    aplicaFiltros();
  }});
}});
document.querySelectorAll('th[data-sort]').forEach(th => {{
  th.addEventListener('click', () => {{
    const key = th.dataset.sort;
    if (sortKey === key) sortAsc = !sortAsc; else {{ sortKey = key; sortAsc = true; }}
    aplicaFiltros();
  }});
}});

renderCustomChips();
aplicaFiltros();
</script>
"""

with open("/tmp/vista_grupo.html", "w", encoding="utf-8") as f:
    f.write(html)

print("OK, escrito", len(html), "bytes")
