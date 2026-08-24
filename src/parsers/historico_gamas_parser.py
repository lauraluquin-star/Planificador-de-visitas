"""
Parser de docs/historico/HISTORICO_GAMAS_23_A_25.xlsx.

Fichero: una fila por POS, con unidades vendidas por gama en 2023/2024/2025 (columnas
"<GAMA> 23/24/25"). ES UNIDADES, no euros -- nunca mezclar con las cifras en euros del
LOB/COMPAR/Acuerdos (CLAUDE.md: "Nunca mezclar EUROS con UNIDADES en un mismo cálculo").

El fichero también trae varias columnas SIN CABECERA (posiciones fijas, ver
_COLUMNAS_SIN_CABECERA) con un número grande que no corresponde a la suma de ninguna
gama vecina -- no se ha podido determinar qué miden, así que se ignoran a propósito
(spec: nunca inventar significado de un dato que no está claro).

Uso principal: tendencia histórica 2023->2024->2025 por marca, para detectar clientes
cuya "buena evolución" de este año es en realidad un rebote tras una caída en 2025
(pedido explícito de la delegada).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import openpyxl

# Gama (tal como aparece en el fichero, sin el sufijo de año) -> marca comercial, solo
# cuando hay confianza razonable (nombre de producto/gama inequívoco, o cruce directo con
# las capturas de Veeva ya validadas). "None" = no se ha podido confirmar la marca --
# nunca se suma a un pacto ni a un total de marca, se muestra aparte.
MARCA_DE_GAMA: dict[str, str | None] = {
    "BIOLOGY": "DUCRAY",
    "ATICAÍDA": "DUCRAY",  # Ducray Anaphase/Anacaps (anticaída) -- confirmado por la delegada
    "EXOMEGA": "A-DERMA",  # cruza con Veeva aderma.exo_exomega
    "KERACNYL": "A-DERMA",
    "CICALFATE": "AVENE",  # cruza con Veeva avene.acz_cicalfate
    "XERACALM": "AVENE",  # cruza con Veeva avene.g029_xeracalm
    "CLEANANCE": "AVENE",  # cruza con Veeva avene.ase_acne
    "ESENCIALES": "AVENE",  # cruza con Veeva avene.ass_soins_essentiels
    "HYDRANCE": "AVENE",  # cruza con Veeva avene.ahy_hydrance
    "ANTIAGE": "AVENE",  # cruza con Veeva avene.g034_dermabsolu
    "ATA": "AVENE",  # Agua Termal Avène -- confirmado por la delegada
    "DEXYANE": "DUCRAY",  # confirmado por la delegada
    "CAPILAR": "DUCRAY",  # confirmado por la delegada (gama distinta de Anticaída/ATICAÍDA -- CLAUDE.md sección 9)
    # Sin confirmar -- no se asigna marca a ciegas (la propia delegada no lo tiene claro):
    "REGENERADORES": None,  # puede ser Avène o A-Derma
    # SOLAR mezcla Avène Solaires + A-Derma Protect sin poder separarlos, y Avène Solar
    # nunca cuenta para Pacto ADA (regla confirmada con la delegada + Acuerdo Comercial real)
    "SOLAR": None,
}

_GAMAS_EN_ORDEN = list(MARCA_DE_GAMA.keys())
_ANIOS = (2023, 2024, 2025)


@dataclass
class HistoricoPOS:
    pos_id: str
    nombre_cliente: str
    # gama -> {2023: unidades|None, 2024: ..., 2025: ...}
    gamas: dict[str, dict[int, int | None]] = field(default_factory=dict)


def parse_historico_gamas(path: str | Path) -> list[HistoricoPOS]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb["LOB GAMAS"]
    filas = ws.iter_rows(values_only=True)
    header = next(filas)

    # índice de columna por (gama, año), ignorando las columnas sin cabecera
    col_por_gama_anio: dict[tuple[str, int], int] = {}
    for i, h in enumerate(header):
        if not h:
            continue
        h = str(h).strip()
        for gama in _GAMAS_EN_ORDEN:
            for anio in _ANIOS:
                sufijo = str(anio)[-2:]
                if h == f"{gama} {sufijo}":
                    col_por_gama_anio[(gama, anio)] = i

    resultado = []
    for row in filas:
        pos_id = row[3]
        if not pos_id:
            continue
        gamas: dict[str, dict[int, int | None]] = {}
        for gama in _GAMAS_EN_ORDEN:
            valores = {}
            for anio in _ANIOS:
                idx = col_por_gama_anio.get((gama, anio))
                valores[anio] = row[idx] if idx is not None else None
            gamas[gama] = valores
        resultado.append(HistoricoPOS(pos_id=str(pos_id).strip(), nombre_cliente=str(row[4] or "").strip(), gamas=gamas))
    return resultado


def historico_por_pos(historico: list[HistoricoPOS]) -> dict[str, HistoricoPOS]:
    return {h.pos_id: h for h in historico}


if __name__ == "__main__":
    historico = parse_historico_gamas("docs/historico/HISTORICO_GAMAS_23_A_25.xlsx")
    print(f"{len(historico)} POS en el histórico de gamas")
    por_pos = historico_por_pos(historico)
    fsp = por_pos.get("C006969")
    if fsp:
        print(f"\n{fsp.nombre_cliente} ({fsp.pos_id}):")
        for gama, valores in fsp.gamas.items():
            marca = MARCA_DE_GAMA[gama] or "sin confirmar"
            print(f"  {gama:16s} [{marca:12s}] 2023={valores[2023]!s:>5} 2024={valores[2024]!s:>5} 2025={valores[2025]!s:>5}")
