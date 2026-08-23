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
    <button class="chip-btn" data-filtro="rojo-ada">🔴 Solo ADA en rojo</button>
    <button class="chip-btn perdidos" data-filtro="perdidos">⚫ Solo ADA perdido</button>
    <input id="buscar" type="text" placeholder="Buscar cliente o población…">
  </div>

  <div class="tabla-panel">
    <table class="cartera" id="tabla">
      <thead>
        <tr>
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
    Sin objetivo de pacto por cliente (eso sale de la Ficha Cliente 2026, que solo tenemos para 2 clientes de ejemplo) — esta vista clasifica solo por evolución YTD vs. año anterior.<br>
    🟢 evolución ≥ 0% · 🟡 entre 0% y −15% · 🔴 por debajo de −15% · ⚪ sin datos suficientes en el LOB · Pacto ADA y Pacto Dexeryl nunca se mezclan
  </div>
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
let soloRojoAda = false;
let soloPerdidosAda = false;
let sortKey = 'ada_evol';
let sortAsc = true;

function aplicaFiltros() {{
  const q = document.getElementById('buscar').value.trim().toLowerCase();
  let filas = DATA.filter(f => {{
    if (grupoActivo !== 'todos') {{
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
  render(filas);
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
    return `<tr class="${{f.perdido_ada ? 'fila-perdida' : ''}}">
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
}}

document.querySelectorAll('.chip-btn[data-grupo]').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('.chip-btn[data-grupo]').forEach(b => b.classList.remove('activo'));
    btn.classList.add('activo');
    grupoActivo = btn.dataset.grupo;
    aplicaFiltros();
  }});
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

aplicaFiltros();
</script>
"""

with open("/tmp/claude-0/-home-user-Planificador-de-visitas/4a7d4b95-3fbe-5a60-b04b-8c2370db4940/scratchpad/vista_grupo.html", "w", encoding="utf-8") as f:
    f.write(html)

print("OK, escrito", len(html), "bytes")
