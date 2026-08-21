"""
Parser del listado LOB (Line Of Business).

Formato real del fichero (verificado sobre datos reales, no supuesto):
- Codificación UTF-16, separado por TABULADORES (no es un CSV estándar con comas).
- Cabecera de 3 filas: grupo (ADA/KF) -> marca -> métrica.
- Cada bloque de marca tiene 5 columnas en este orden:
    Importe Neto 2025, Objetivo 2026, Importe Neto YTD-1, Importe Neto YTD, Evol YTD/YTD-1

Reglas de negocio aplicadas (ver CLAUDE.md y docs/00_SPEC_MAESTRA.md):
- La columna "ADA > Total" del fichero NO es el Pacto ADA: mezcla Avène+Ducray+A-Derma+Dexeryl
  (verificado matemáticamente sobre datos reales). Por eso el Pacto ADA se recalcula aquí a partir
  de las 4 marcas individuales, ignorando esa columna.
- La columna "KF > Total" SÍ es fiable (verificado: = Furterer+Klorane+Hermesetas+Cysticlean+Meme).
- El objetivo real del Pacto ADA/Dexeryl/KF NO sale de este fichero (sale de la Ficha Cliente 2026).
  El "Objetivo 2026" que trae el LOB se conserva solo como referencia de seguimiento (LOB = económico
  y evolución, nunca fuente de objetivo de pacto -- sección 6 de la spec).
- Klorane/Furterer/Hermesetas/Cysticlean/Meme se modelan como PACTO_KF independiente: se parsean y
  guardan igual que ADA/Dexeryl, pero el motor de negocio actual no debe usarlos para calcular
  objetivos, gaps ni recomendaciones (CLAUDE.md: "Klorane NUNCA se usa para calcular...").
- Identidad física del punto de venta = dirección + código postal + población (nunca solo el POS-Id,
  que puede cambiar -- sección 7 de la spec).
"""

from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

# Bloques de columnas (0-indexed) confirmados sobre el fichero real.
# Cada bloque = (importe_neto_2025, objetivo_2026, importe_neto_ytd1, importe_neto_ytd, evol_ytd_ytd1)
MARCA_BLOQUES = {
    "ada_total_bruto": 13,  # NO USAR como Pacto ADA -- incluye Dexeryl. Se conserva solo para auditoría.
    "avene_sin_solar": 18,
    "avene_solar": 23,
    "ducray": 28,
    "aderma": 33,
    "dexeryl": 38,
    "kf_total": 43,  # Sí fiable: Furterer+Klorane+Hermesetas+Cysticlean+Meme
    "furterer": 48,
    "klorane": 53,
    "hermesetas": 58,
    "cysticlean": 63,
    "meme": 68,
}

METRICAS = ["importe_neto_2025", "objetivo_2026_lob_referencia", "importe_neto_ytd1", "importe_neto_ytd", "evol_ytd_pct"]

MARCAS_ADA = ["avene_sin_solar", "avene_solar", "ducray", "aderma"]
MARCAS_KF = ["furterer", "klorane", "hermesetas", "cysticlean", "meme"]


def _normaliza_texto(s: str | float | None) -> str:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    s = str(s).strip().upper()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"\s+", " ", s)
    return s


def identidad_fisica_id(direccion: str, cp: str, poblacion: str) -> str:
    """Identidad del punto de venta: dirección + CP + población (nunca el POS-Id, que puede cambiar)."""
    return f"{_normaliza_texto(direccion)}|{_normaliza_texto(cp)}|{_normaliza_texto(poblacion)}"


def _to_importe(valor: str | float | None) -> float | None:
    """Convierte '70.294' (miles con punto) -> 70294.0. Vacío/NaN -> None (N/D, no 0)."""
    if valor is None:
        return None
    if isinstance(valor, float) and pd.isna(valor):
        return None
    s = str(valor).strip()
    if s == "" or s.lower() == "nan":
        return None
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _to_evol_pct(valor: str | float | None) -> float | None:
    """Convierte '-72%' -> -0.72. Vacío/NaN -> None."""
    if valor is None:
        return None
    if isinstance(valor, float) and pd.isna(valor):
        return None
    s = str(valor).strip().replace("%", "").replace(",", ".")
    if s == "" or s.lower() == "nan":
        return None
    try:
        return float(s) / 100.0
    except ValueError:
        return None


@dataclass
class MedidaMarca:
    """Cifras de una marca para un cliente, tal como vienen del LOB."""

    importe_neto_2025: float | None
    objetivo_2026_lob_referencia: float | None  # NO es el objetivo de pacto real (eso viene de Ficha 2026)
    importe_neto_ytd1: float | None
    importe_neto_ytd: float | None
    evol_ytd_pct: float | None
    estado: str  # "OK" si hay datos, "ND" si el cliente no tiene relación con esta marca en el LOB


@dataclass
class PactoAgregado:
    """Agregado de un pacto (ADA, DEXERYL o KF) a partir de las marcas que lo componen."""

    importe_neto_2025: float | None
    importe_neto_ytd1: float | None
    importe_neto_ytd: float | None
    marcas_incluidas: list[str]


@dataclass
class ClienteLOB:
    coach: str
    dnv: str
    dr: str
    sales_unit: str
    delegado_nombre: str
    delegado_lob_code: str
    pos_id: str
    nombre_cliente: str
    direccion: str
    codigo_postal: str
    provincia: str
    poblacion: str
    grupo_compra: str
    fecha_ultimo_pedido: str
    identidad_fisica_id: str
    marcas: dict[str, MedidaMarca] = field(default_factory=dict)
    pacto_ada: PactoAgregado | None = None
    pacto_dexeryl: PactoAgregado | None = None
    pacto_kf: PactoAgregado | None = None


def _suma_pacto(marcas: dict[str, MedidaMarca], nombres: list[str]) -> PactoAgregado:
    def suma(campo: str) -> float | None:
        valores = [getattr(marcas[m], campo) for m in nombres if marcas[m].estado == "OK"]
        if not valores:
            return None
        return round(sum(valores), 2)

    return PactoAgregado(
        importe_neto_2025=suma("importe_neto_2025"),
        importe_neto_ytd1=suma("importe_neto_ytd1"),
        importe_neto_ytd=suma("importe_neto_ytd"),
        marcas_incluidas=nombres,
    )


def _parse_fila(row: list[str]) -> ClienteLOB:
    marcas: dict[str, MedidaMarca] = {}
    for nombre_marca, col_inicio in MARCA_BLOQUES.items():
        if nombre_marca == "ada_total_bruto":
            continue  # se conserva aparte, no es una "marca"
        crudos = row[col_inicio : col_inicio + 5]
        valores = [
            _to_importe(crudos[0]),
            _to_importe(crudos[1]),
            _to_importe(crudos[2]),
            _to_importe(crudos[3]),
            _to_evol_pct(crudos[4]),
        ]
        estado = "OK" if any(v is not None for v in valores) else "ND"
        marcas[nombre_marca] = MedidaMarca(*valores, estado=estado)

    cliente = ClienteLOB(
        coach=row[0],
        dnv=row[1],
        dr=row[1],
        sales_unit=row[2],
        delegado_nombre=row[3],
        delegado_lob_code=row[4],
        pos_id=row[5],
        nombre_cliente=row[6],
        direccion=row[7],
        codigo_postal=row[8],
        provincia=row[9],
        poblacion=row[10],
        grupo_compra=row[11],
        fecha_ultimo_pedido=row[12],
        identidad_fisica_id=identidad_fisica_id(row[7], row[8], row[10]),
        marcas=marcas,
    )
    cliente.pacto_ada = _suma_pacto(marcas, MARCAS_ADA)
    cliente.pacto_dexeryl = _suma_pacto(marcas, ["dexeryl"])
    cliente.pacto_kf = _suma_pacto(marcas, MARCAS_KF)
    return cliente


def parse_lob(path: str | Path) -> list[ClienteLOB]:
    """Lee el fichero LOB real (UTF-16, tabulador, cabecera de 3 filas) y devuelve una lista de clientes.

    Usa el módulo csv (no un split("\\t") ingenuo) porque algunas direcciones vienen entrecomilladas
    con un salto de línea dentro (ej. "NACIONAL 152 KM 169,74\\n(CTRA VILALLOBENT)"): un split línea a
    línea las parte en dos registros corruptos y pierde clientes en silencio.
    """
    with open(path, encoding="utf-16", newline="") as f:
        for _ in range(3):
            next(f)  # descarta las 3 filas de cabecera (grupo / marca / métrica)
        filas = list(csv.reader(f, delimiter="\t", quotechar='"'))

    descartadas = [fila for fila in filas if not (len(fila) >= 73 and fila[5].strip())]
    if descartadas:
        print(f"[parse_lob] Aviso: {len(descartadas)} filas descartadas por no tener 73 columnas o POS-Id vacío.")

    return [_parse_fila(fila) for fila in filas if len(fila) >= 73 and fila[5].strip()]


if __name__ == "__main__":
    import sys

    ruta = sys.argv[1] if len(sys.argv) > 1 else "docs/lob_compar/Listado_LOB_03_08_26.csv"
    clientes = parse_lob(ruta)
    print(f"Clientes parseados: {len(clientes)}")

    # Validación con datos reales: CUCUPHARMA (POS C013997), verificado a mano en la exploración inicial.
    for c in clientes:
        if c.pos_id == "C013997":
            print("\n--- Ejemplo real: CUCUPHARMA S.L. (C013997) ---")
            print("Identidad física:", c.identidad_fisica_id)
            print("Pacto ADA (Avène+Ducray+A-Derma, sin Dexeryl):", c.pacto_ada)
            print("Pacto DEXERYL:", c.pacto_dexeryl)
            print("Pacto KF (Furterer+Klorane+Hermesetas+Cysticlean+Meme):", c.pacto_kf)
            break
