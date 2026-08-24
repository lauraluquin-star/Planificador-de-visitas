"""
Tendencia histórica 2023-2025 por marca, a partir de docs/historico/HISTORICO_GAMAS_23_A_25.xlsx.

Sirve para responder a algo que el YTD/objetivo en euros no puede mostrar por sí solo:
si la "buena evolución" de este año es una recuperación real o simplemente el rebote tras
una caída en 2025 (pedido explícito de la delegada, 24/08/2026).

Son UNIDADES históricas -- no se combinan ni se sustituyen con las cifras en euros del
Pacto ADA/Dexeryl (CLAUDE.md: nunca mezclar euros y unidades). Se presentan como una vista
aparte, en paralelo.

Reutiliza el mismo criterio de "pos_ids vivos" que ya usa el motor de objetivo/gap para no
duplicar histórico de un pos_id fantasma tras un cambio de titular.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.parsers.historico_gamas_parser import MARCA_DE_GAMA, HistoricoPOS

MARCAS_CON_TENDENCIA = ("AVENE", "DUCRAY", "A-DERMA")
_ANIOS = (2023, 2024, 2025)


@dataclass
class TendenciaCliente:
    por_marca: dict[str, dict[int, int]]  # marca -> {2023: uds, 2024: uds, 2025: uds}
    gamas_sin_marca_confirmada: dict[str, dict[int, int]]  # gama -> {2023: uds, ...}
    pos_ids_con_historico: list[str]
    pos_ids_sin_historico: list[str]


def tendencia_cliente(pos_ids: list[str], historico_por_pos: dict[str, HistoricoPOS]) -> TendenciaCliente:
    por_marca = {m: {a: 0 for a in _ANIOS} for m in MARCAS_CON_TENDENCIA}
    sin_marca: dict[str, dict[int, int]] = {}
    con_historico, sin_historico = [], []

    for pos_id in pos_ids:
        h = historico_por_pos.get(pos_id)
        if h is None:
            sin_historico.append(pos_id)
            continue
        con_historico.append(pos_id)
        for gama, valores in h.gamas.items():
            marca = MARCA_DE_GAMA[gama]
            destino = por_marca[marca] if marca in por_marca else sin_marca.setdefault(gama, {a: 0 for a in _ANIOS})
            for anio in _ANIOS:
                destino[anio] += valores[anio] or 0

    return TendenciaCliente(
        por_marca=por_marca,
        gamas_sin_marca_confirmada=sin_marca,
        pos_ids_con_historico=con_historico,
        pos_ids_sin_historico=sin_historico,
    )


def evol_pct(v_ini: int, v_fin: int) -> float | None:
    if not v_ini:
        return None
    return round((v_fin - v_ini) / v_ini * 100, 1)


if __name__ == "__main__":
    import sys

    sys.path.insert(0, ".")
    from src.parsers.historico_gamas_parser import historico_por_pos, parse_historico_gamas

    historico = historico_por_pos(parse_historico_gamas("docs/historico/HISTORICO_GAMAS_23_A_25.xlsx"))
    t = tendencia_cliente(["C006969"], historico)
    print("FONT SOLER PILAR -- tendencia 2023-2025 (unidades):")
    for marca, valores in t.por_marca.items():
        print(f"  {marca:10s} 2023={valores[2023]:4d}  2024={valores[2024]:4d}  2025={valores[2025]:4d}  "
              f"evol23-24={evol_pct(valores[2023], valores[2024])}%  evol24-25={evol_pct(valores[2024], valores[2025])}%")
