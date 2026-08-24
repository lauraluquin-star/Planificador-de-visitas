"""
Genera un informe de "Análisis de Grupo" para una visita conjunta a varias farmacias que compran
juntas (grupo informal, no un "Grupo Compra" oficial del LOB) -- p.ej. la visita del 2 de septiembre
con la jefa a 4 farmacias. Reutiliza el motor y la serialización ya validados; no recalcula nada
propio.

Uso: editar NOMBRES_GRUPO abajo (substring en mayúsculas contra nombre_cliente) y ejecutar.
"""

from __future__ import annotations

import json
import sys

sys.path.insert(0, ".")

from src.engine.comparacion import PuntoVentaConsolidado, cartera_delegado
from src.engine.tendencia_historica import MARCAS_CON_TENDENCIA, tendencia_cliente
from src.engine.tendencia_historica import evol_pct as evol_pct_unidades
from src.parsers.acuerdos_parser import objetivos_por_pos_id, parse_acuerdos
from src.parsers.historico_gamas_parser import historico_por_pos, parse_historico_gamas
from src.parsers.lob_parser import parse_lob
from src.serializacion import NOMBRE_MARCA, fila_cliente

NOMBRES_GRUPO = ["GORDILLO ABALOS", "TUDELA BELDA", "MONTENEGRO GUIJALBA", "RUBIO PETIT"]
DELEGADO = "LAURA LUQUIN FRANQUET"

MARCAS_COMBINADAS = ["avene_sin_solar", "avene_solar", "ducray", "aderma", "dexeryl"]
MARCA_COMERCIAL_A_LOB = {"AVENE": "avene_sin_solar", "DUCRAY": "ducray", "A-DERMA": "aderma", "DEXERYL": "dexeryl"}


def fmt_eur(v):
    if v is None:
        return "—"
    return f"{v:,.0f} €".replace(",", ".")


def evol_pct(ytd1, ytd):
    if not ytd1:
        return None
    return round((ytd - ytd1) / ytd1 * 100, 1)


def clasifica(evol):
    if evol is None:
        return "SIN_DATOS", "⚪"
    if evol >= 0:
        return "POSITIVA", "🟢"
    if evol >= -15:
        return "NEGATIVA_CONTROLADA", "🟡"
    return "NEGATIVA", "🔴"


def main():
    clientes = parse_lob("docs/lob_compar/Listado_LOB_03_08_26.csv")
    acuerdos = parse_acuerdos("docs/acuerdos_comerciales/Listado_Acuerdos_Comerciales_LIVE.csv")
    objetivos = objetivos_por_pos_id(acuerdos)
    cartera = cartera_delegado(clientes, DELEGADO, consolidar=True, objetivos_por_pos=objetivos)
    historico = historico_por_pos(parse_historico_gamas("docs/historico/HISTORICO_GAMAS_23_A_25.xlsx"))

    resumenes = [r for r in cartera if any(n in r.cliente.nombre_cliente.upper() for n in NOMBRES_GRUPO)]
    filas = [fila_cliente(r, i, objetivos) for i, r in enumerate(resumenes)]
    if len(filas) != len(NOMBRES_GRUPO):
        print(f"AVISO: se esperaban {len(NOMBRES_GRUPO)} farmacias y se encontraron {len(filas)}", file=sys.stderr)

    combinado_tendencia = {m: {2023: 0, 2024: 0, 2025: 0} for m in MARCAS_CON_TENDENCIA}
    for i, r in enumerate(resumenes):
        pos_ids = r.cliente.pos_ids if isinstance(r.cliente, PuntoVentaConsolidado) else [r.cliente.pos_id]
        t = tendencia_cliente(pos_ids, historico)
        filas[i]["tendencia_23_25"] = {
            "por_marca": {
                m: {"valores": v, "evol_23_24": evol_pct_unidades(v[2023], v[2024]), "evol_24_25": evol_pct_unidades(v[2024], v[2025])}
                for m, v in t.por_marca.items()
            },
            "pos_ids_sin_historico": t.pos_ids_sin_historico,
        }
        for m, v in t.por_marca.items():
            for anio in (2023, 2024, 2025):
                combinado_tendencia[m][anio] += v[anio]

    def suma(campo):
        vals = [f[campo] for f in filas if f[campo] is not None]
        return round(sum(vals), 2) if vals else None

    ada_ytd1, ada_ytd = suma("ada_ytd1"), suma("ada_ytd")
    dex_ytd1, dex_ytd = suma("dex_ytd1"), suma("dex_ytd")
    ada_obj, ada_gap = suma("ada_objetivo"), suma("ada_gap")
    dex_obj, dex_gap = suma("dex_objetivo"), suma("dex_gap")
    ada_evol = evol_pct(ada_ytd1, ada_ytd)
    dex_evol = evol_pct(dex_ytd1, dex_ytd)
    ada_estado, ada_semaforo = clasifica(ada_evol)
    dex_estado, dex_semaforo = clasifica(dex_evol)
    ada_cumpl = round(ada_ytd / ada_obj * 100, 1) if ada_obj else None
    dex_cumpl = round(dex_ytd / dex_obj * 100, 1) if dex_obj else None

    marcas_combinadas = {}
    for m in MARCAS_COMBINADAS:
        ytd1 = sum(f["marcas"][m]["ytd1"] or 0 for f in filas)
        ytd = sum(f["marcas"][m]["ytd"] or 0 for f in filas)
        marcas_combinadas[m] = {"ytd1": ytd1, "ytd": ytd, "evol": evol_pct(ytd1, ytd)}

    objetivo_por_marca_comb = {}
    for k in ("AVENE", "DUCRAY", "A-DERMA", "DEXERYL"):
        vals = [f["objetivo_por_marca"][k] for f in filas if f["objetivo_por_marca"][k] is not None]
        objetivo_por_marca_comb[k] = round(sum(vals), 2) if vals else None

    data = {
        "delegado": DELEGADO,
        "farmacias": filas,
        "grupo": {
            "ada_ytd1": ada_ytd1, "ada_ytd": ada_ytd, "ada_evol": ada_evol, "ada_estado": ada_estado, "ada_semaforo": ada_semaforo,
            "ada_objetivo": ada_obj, "ada_gap": ada_gap, "ada_cumplimiento": ada_cumpl,
            "dex_ytd1": dex_ytd1, "dex_ytd": dex_ytd, "dex_evol": dex_evol, "dex_estado": dex_estado, "dex_semaforo": dex_semaforo,
            "dex_objetivo": dex_obj, "dex_gap": dex_gap, "dex_cumplimiento": dex_cumpl,
            "marcas": marcas_combinadas,
            "objetivo_por_marca": objetivo_por_marca_comb,
            "tendencia_23_25": {
                m: {"valores": v, "evol_23_24": evol_pct_unidades(v[2023], v[2024]), "evol_24_25": evol_pct_unidades(v[2024], v[2025])}
                for m, v in combinado_tendencia.items()
            },
        },
    }
    with open("/tmp/grupo_visita_2_sept.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"OK: {len(filas)} farmacias -> /tmp/grupo_visita_2_sept.json")


if __name__ == "__main__":
    main()
