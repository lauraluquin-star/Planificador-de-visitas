import json

with open("/tmp/grupo_visita_2_sept.json", encoding="utf-8") as f:
    data = json.load(f)

g = data["grupo"]
farmacias = data["farmacias"]

def fmt_eur(v):
    if v is None:
        return "—"
    return f"{v:,.0f} €".replace(",", ".")

def fmt_pct(v):
    if v is None:
        return "N/D"
    return f"{'+' if v >= 0 else ''}{v:.1f} %".replace(".", ",")

def semaforo(estado):
    return {"POSITIVA": "🟢", "NEGATIVA_CONTROLADA": "🟡", "NEGATIVA": "🔴", "SIN_DATOS": "⚪"}.get(estado, "⚪")

def evol_cls(v):
    if v is None:
        return "nd"
    if v >= 0:
        return "pos"
    if v >= -15:
        return "neg-c"
    return "neg"

NOMBRE_MARCA = {
    "avene_sin_solar": "Avène (sin solar)",
    "avene_solar": "Avène Solar (aparte del Pacto ADA)",
    "ducray": "Ducray",
    "aderma": "A-Derma",
    "dexeryl": "Dexeryl",
}
MARCA_LOB_A_COMERCIAL = {"avene_sin_solar": "AVENE", "ducray": "DUCRAY", "aderma": "A-DERMA", "dexeryl": "DEXERYL"}

def fila_marca_grupo(key):
    label = NOMBRE_MARCA[key]
    m = g["marcas"][key]
    clave = MARCA_LOB_A_COMERCIAL.get(key)
    objetivo = g["objetivo_por_marca"].get(clave) if clave else None
    if objetivo is None:
        celda_obj = '<span style="color:var(--ink-soft)">—</span>'
        celda_falta = '<span style="color:var(--ink-soft)">aparte del pacto</span>'
    else:
        falta = objetivo - m["ytd"]
        falta_txt = f"−{fmt_eur(falta)}" if falta > 0 else f"+{fmt_eur(-falta)}"
        falta_cls = "neg" if falta > 0 else "pos"
        celda_obj = fmt_eur(objetivo)
        celda_falta = f'<span class="evol {falta_cls}">{falta_txt}</span>'
    return f"""<tr>
      <td class="nombre-marca-cell">{label}</td>
      <td class="num">{fmt_eur(m['ytd1'])}</td>
      <td class="num">{fmt_eur(m['ytd'])}</td>
      <td class="num"><span class="evol {evol_cls(m['evol'])}">{fmt_pct(m['evol'])}</span></td>
      <td class="num">{celda_obj}</td>
      <td class="num">{celda_falta}</td>
    </tr>"""

marcas_grupo_html = "\n".join(fila_marca_grupo(k) for k in ["avene_sin_solar", "avene_solar", "ducray", "aderma", "dexeryl"])

def tarjeta_cliente(f):
    ada_info_cls = evol_cls(f["ada_evol"])
    dex_info_cls = evol_cls(f["dex_evol"])
    pos_txt = " + ".join(f["pos_ids"])
    badges = []
    if f["n_pos"] > 1:
        badges.append(f'{f["n_pos"]} POS-Id consolidados')
    if f["perdido_ada"]:
        badges.append("⚫ ADA perdido")
    if f["perdido_dex"]:
        badges.append("⚫ Dexeryl perdido")
    badges_html = "".join(f'<span class="chip">{b}</span>' for b in badges)

    ada_obj_txt = (
        f'Objetivo: <b>{fmt_eur(f["ada_objetivo"])}</b> · cumplimiento <b>{f["ada_pct_cumplimiento"]}%</b> · gap <b>{fmt_eur(f["ada_gap"])}</b>'
        if f["ada_objetivo"] is not None
        else "Objetivo no disponible (sin acuerdo Activo)"
    )
    dex_obj_txt = (
        f'Objetivo: <b>{fmt_eur(f["dex_objetivo"])}</b> · cumplimiento <b>{f["dex_pct_cumplimiento"]}%</b> · gap <b>{fmt_eur(f["dex_gap"])}</b>'
        if f["dex_objetivo"] is not None
        else "Objetivo no disponible (sin acuerdo Activo)"
    )

    return f"""
    <div class="cliente-card">
      <div class="cliente-head">
        <div>
          <div class="cliente-nombre">{f["nombre"]}</div>
          <div class="cliente-sub">{f["direccion"]}, {f["poblacion"]} · {pos_txt}</div>
        </div>
        <div class="chip-row">{badges_html}</div>
      </div>
      <div class="cliente-pactos">
        <div class="cliente-pacto">
          <div class="cliente-pacto-nombre">Pacto ADA</div>
          <div class="cliente-pacto-linea">{fmt_eur(f['ada_ytd1'])} → {fmt_eur(f['ada_ytd'])} &nbsp; {semaforo(f['ada_estado'])} <span class="evol {ada_info_cls}">{fmt_pct(f['ada_evol'])}</span></div>
          <div class="cliente-pacto-obj">{ada_obj_txt}</div>
        </div>
        <div class="cliente-pacto">
          <div class="cliente-pacto-nombre">Pacto Dexeryl</div>
          <div class="cliente-pacto-linea">{fmt_eur(f['dex_ytd1'])} → {fmt_eur(f['dex_ytd'])} &nbsp; {semaforo(f['dex_estado'])} <span class="evol {dex_info_cls}">{fmt_pct(f['dex_evol'])}</span></div>
          <div class="cliente-pacto-obj">{dex_obj_txt}</div>
        </div>
      </div>
    </div>"""

clientes_html = "\n".join(tarjeta_cliente(f) for f in farmacias)

nombres_titulo = " · ".join(f["nombre"].title() for f in farmacias)

html = f"""<title>Análisis de Grupo — Visita 2 septiembre</title>
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
.page {{ max-width: 820px; margin: 0 auto; padding: 20px 16px 64px; display: flex; flex-direction: column; gap: 16px; }}

.masthead {{ background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 18px 20px; box-shadow: var(--shadow); }}
.eyebrow {{ font-family: 'IBM Plex Mono', monospace; font-size: 11px; letter-spacing: 0.09em; text-transform: uppercase; color: var(--accent); font-weight: 600; }}
.titulo {{ font-family: 'Newsreader', Georgia, serif; font-weight: 600; font-size: clamp(20px, 4vw, 26px); text-wrap: balance; margin: 2px 0 0; }}
.subt {{ font-size: 13.5px; color: var(--ink-soft); margin-top: 6px; }}

.section-title {{ font-family: 'Newsreader', Georgia, serif; font-size: 15px; font-weight: 600; font-style: italic; color: var(--ink-soft); margin: 4px 2px 0; }}

.pactos {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
@media (max-width: 560px) {{ .pactos {{ grid-template-columns: 1fr; }} }}
.pacto-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 16px 18px; box-shadow: var(--shadow); display: flex; flex-direction: column; gap: 8px; }}
.pacto-head {{ display: flex; justify-content: space-between; align-items: center; }}
.pacto-name {{ font-family: 'Newsreader', Georgia, serif; font-weight: 600; font-size: 17px; }}
.pacto-num {{ font-family: 'IBM Plex Mono', monospace; font-size: 24px; font-weight: 600; }}
.pacto-linea {{ font-size: 13px; color: var(--ink-soft); display: flex; justify-content: space-between; }}
.pacto-linea b {{ color: var(--ink); font-family: 'IBM Plex Mono', monospace; }}
.pacto-fuente {{ font-family: 'IBM Plex Mono', monospace; font-size: 10.5px; color: var(--ink-soft); border-top: 1px dashed var(--border); padding-top: 8px; margin-top: 2px; }}

.tabla-panel {{ background: var(--surface); border: 1px solid var(--border); border-radius: 14px; box-shadow: var(--shadow); overflow-x: auto; padding: 4px; }}
table.marcas {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
table.marcas th {{ text-align: left; font-size: 10px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--ink-soft); font-weight: 600; padding: 10px 10px; border-bottom: 1px solid var(--border); font-family: 'IBM Plex Mono', monospace; }}
table.marcas td {{ padding: 9px 10px; border-bottom: 1px solid var(--border); font-family: 'IBM Plex Mono', monospace; white-space: nowrap; }}
table.marcas td.nombre-marca-cell {{ font-family: 'IBM Plex Sans', sans-serif; }}
table.marcas th.num, table.marcas td.num {{ text-align: right; }}
.evol {{ font-weight: 600; }}
.evol.pos {{ color: var(--ok); }} .evol.neg-c {{ color: var(--warn); }} .evol.neg {{ color: var(--bad); }} .evol.nd {{ color: var(--nd); }}

.cliente-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 16px 18px; box-shadow: var(--shadow); display: flex; flex-direction: column; gap: 12px; }}
.cliente-head {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; flex-wrap: wrap; }}
.cliente-nombre {{ font-family: 'Newsreader', Georgia, serif; font-weight: 600; font-size: 18px; }}
.cliente-sub {{ font-size: 12.5px; color: var(--ink-soft); margin-top: 2px; }}
.chip-row {{ display: flex; gap: 6px; flex-wrap: wrap; }}
.chip {{ font-family: 'IBM Plex Mono', monospace; font-size: 10.5px; padding: 3px 8px; border-radius: 999px; border: 1px solid var(--border); color: var(--ink-soft); background: var(--surface-2); white-space: nowrap; }}
.cliente-pactos {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
@media (max-width: 480px) {{ .cliente-pactos {{ grid-template-columns: 1fr; }} }}
.cliente-pacto {{ border: 1px solid var(--border); border-radius: 10px; padding: 10px 12px; }}
.cliente-pacto-nombre {{ font-family: 'IBM Plex Mono', monospace; font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--ink-soft); font-weight: 600; margin-bottom: 4px; }}
.cliente-pacto-linea {{ font-size: 13px; font-family: 'IBM Plex Mono', monospace; }}
.cliente-pacto-obj {{ font-size: 11.5px; color: var(--ink-soft); margin-top: 6px; border-top: 1px dashed var(--border); padding-top: 6px; }}
.cliente-pacto-obj b {{ color: var(--ink); font-family: 'IBM Plex Mono', monospace; }}

.notas-panel {{ background: var(--surface); border: 1px solid var(--accent); border-radius: 14px; padding: 16px 18px; box-shadow: var(--shadow); }}
.notas-panel ol {{ margin: 8px 0 0; padding-left: 20px; display: flex; flex-direction: column; gap: 8px; }}
.notas-panel li {{ font-size: 13.5px; }}

.footer-note {{ font-size: 11.5px; color: var(--ink-soft); text-align: center; padding: 4px 12px 0; font-family: 'IBM Plex Mono', monospace; line-height: 1.6; }}
</style>

<div class="page">
  <div class="masthead">
    <span class="eyebrow">Análisis de grupo · Visita 2 de septiembre</span>
    <h1 class="titulo">{nombres_titulo}</h1>
    <div class="subt">4 farmacias que compran en grupo (agrupación informal, no un Grupo Compra oficial del LOB) — análisis conjunto con datos reales: LOB corte 03/08/2026 + Acuerdos Comerciales LIVE.</div>
  </div>

  <div class="section-title">Pactos combinados del grupo</div>
  <div class="pactos">
    <div class="pacto-card">
      <div class="pacto-head"><span class="pacto-name">Pacto ADA</span><span class="pacto-num">{semaforo(g['ada_estado'])}</span></div>
      <div class="pacto-linea"><span>2025 → 2026</span><b>{fmt_eur(g['ada_ytd1'])} → {fmt_eur(g['ada_ytd'])}</b></div>
      <div class="pacto-linea"><span>Evolución</span><span class="evol {evol_cls(g['ada_evol'])}">{fmt_pct(g['ada_evol'])}</span></div>
      <div class="pacto-linea"><span>Objetivo combinado</span><b>{fmt_eur(g['ada_objetivo'])}</b></div>
      <div class="pacto-linea"><span>Cumplimiento</span><b>{g['ada_cumplimiento']}%</b></div>
      <div class="pacto-linea"><span>Gap combinado</span><b style="color:var(--bad)">{fmt_eur(g['ada_gap'])}</b></div>
      <div class="pacto-fuente">Avène (sin solar) + Ducray + A-Derma de las 4 farmacias · objetivo: suma de sus acuerdos Activos reales</div>
    </div>
    <div class="pacto-card">
      <div class="pacto-head"><span class="pacto-name">Pacto Dexeryl</span><span class="pacto-num">{semaforo(g['dex_estado'])}</span></div>
      <div class="pacto-linea"><span>2025 → 2026</span><b>{fmt_eur(g['dex_ytd1'])} → {fmt_eur(g['dex_ytd'])}</b></div>
      <div class="pacto-linea"><span>Evolución</span><span class="evol {evol_cls(g['dex_evol'])}">{fmt_pct(g['dex_evol'])}</span></div>
      <div class="pacto-linea"><span>Objetivo combinado</span><b>{fmt_eur(g['dex_objetivo'])}</b></div>
      <div class="pacto-linea"><span>Cumplimiento</span><b>{g['dex_cumplimiento']}%</b></div>
      <div class="pacto-linea"><span>Gap combinado</span><b style="color:var(--bad)">{fmt_eur(g['dex_gap'])}</b></div>
      <div class="pacto-fuente">Independiente del Pacto ADA · objetivo: suma de sus acuerdos Activos reales</div>
    </div>
  </div>

  <div class="section-title">Desglose y objetivo por marca (grupo combinado)</div>
  <div class="tabla-panel">
    <table class="marcas">
      <thead><tr><th>Marca</th><th class="num">2025</th><th class="num">2026</th><th class="num">Evol.</th><th class="num">Objetivo</th><th class="num">Falta</th></tr></thead>
      <tbody>{marcas_grupo_html}</tbody>
    </table>
  </div>

  <div class="notas-panel">
    <div class="section-title" style="margin:0;">Notas para la visita</div>
    <ol>
      <li><strong>El grupo está al 36% del objetivo combinado de Pacto ADA</strong> (9.530€ de 26.480€, faltan 16.950€) — con evolución −19,8% vs. año anterior. Merece una conversación conjunta sobre qué está pasando en las 4 a la vez, no solo visitas sueltas.</li>
      <li><strong>Tudela Belda Alberto ha perdido Dexeryl</strong> (75€ → 0€, 0 real este año) — el único de los 4 con un pacto realmente perdido. Su Pacto ADA también cae fuerte (−82,3%).</li>
      <li><strong>Gordillo Abalos M. Jesus es el único que crece</strong> en Pacto ADA (+5,1%) — el ejemplo positivo del grupo, útil para contrastar con el resto.</li>
      <li><strong>Avène Solar del grupo está prácticamente estable</strong> (−4,5%) — a diferencia de otros casos vistos en la cartera, aquí no es la campaña la que arrastra el gap: el problema está en Avène sin solar, Ducray y A-Derma.</li>
      <li>Dexeryl combinado está muy por debajo de objetivo en las 4 (11,2% de cumplimiento) — posible punto de conversación conjunta con el grupo sobre esta marca en concreto.</li>
    </ol>
  </div>

  <div class="section-title">Detalle por farmacia</div>
  {clientes_html}

  <div class="footer-note">
    Datos reales: LOB (corte 03/08/2026) · Acuerdos Comerciales LIVE (objetivo real de pacto) · Sin captura de Veeva para estas 4 farmacias — no se muestran oportunidades por gama.<br>
    Pacto ADA y Pacto Dexeryl nunca se mezclan · Avène Solar nunca cuenta para el Pacto ADA.
  </div>
</div>
"""

with open("/tmp/grupo_visita_2_sept.html", "w", encoding="utf-8") as f:
    f.write(html)

print("OK, escrito", len(html), "bytes")
