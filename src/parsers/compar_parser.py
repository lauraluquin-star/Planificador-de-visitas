"""
Parser de los ficheros COMPAR (evolución histórica por punto de venta).

Cada COMPAR es una fotografía a una fecha de referencia concreta. Verificado sobre datos reales:

- COMPAR_16_OCTUBRE_2025.xlsx -> hoja "LISTADO CLIENTES". Compara YTD 2024 vs YTD 2025 (mismo corte,
  año distinto). Trae Avène combinado (SIN_SOLAR+SOLAR, verificado: coincide al 100%) y también el
  desglose. Incluye columnas de Furterer/Klorane/Hermesetas/Cysticlean (grupo KF).
  Su columna "TOTAL" mezcla TODO: ADA + DEXERYL + KF (verificado matemáticamente, 100% de coincidencia
  sobre las filas con los 8 componentes presentes). No usar nunca como Pacto ADA.

- COMPAR_JUNIO_2026.xlsx -> hoja "INFORME DE VENTAS JUNIO 2026". Compara YTD 2025 vs YTD 2026 (mismo
  corte). NO incluye columnas de Furterer/Klorane/Hermesetas/Cysticlean en esta hoja -- el grupo KF
  simplemente no está disponible en esta fuente para clientes (a diferencia del COMPAR de octubre).
  Su columna "TOTAL" mezcla ADA + DEXERYL (verificado 100% sobre las filas completas). Tampoco usar
  como Pacto ADA.

En ambos casos, igual que en el LOB, el Pacto ADA se recalcula aquí sumando Avène(combinado)+Ducray+
A-Derma, ignorando la columna "TOTAL" del fichero de origen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .lob_parser import identidad_fisica_id


def _num(v) -> float | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


@dataclass
class MedidaMarcaCompar:
    valor_anio_completo_anterior: float | None  # ej. TOTAL 2024, o AVENE 2025 (año fiscal completo)
    ytd_comparable_anio_anterior: float | None  # YTD del año anterior, mismo corte de fecha
    ytd_actual: float | None  # YTD del año de referencia del COMPAR, mismo corte
    evol_pct: float | None
    oportunidad: bool
    estado: str  # "OK" o "ND"


@dataclass
class PactoComparAgregado:
    ytd_comparable_anio_anterior: float | None
    ytd_actual: float | None
    marcas_incluidas: list[str]
    disponible: bool  # False si la fuente no trae ninguna de las marcas de este pacto (ej. KF en Junio)


@dataclass
class ClienteCompar:
    fecha_referencia: str  # "OCT_2025" | "JUN_2026"
    coach: str
    zona: str | None
    lob_code: str
    pos_id: str
    nombre_cliente: str
    direccion: str
    codigo_postal: str
    provincia: str
    poblacion: str
    identidad_fisica_id: str
    marcas: dict[str, MedidaMarcaCompar] = field(default_factory=dict)
    pacto_ada: PactoComparAgregado | None = None
    pacto_dexeryl: PactoComparAgregado | None = None
    pacto_kf: PactoComparAgregado | None = None


def _pacto(marcas: dict[str, MedidaMarcaCompar], nombres: list[str]) -> PactoComparAgregado:
    presentes = [n for n in nombres if n in marcas and marcas[n].estado == "OK"]
    if not presentes:
        return PactoComparAgregado(None, None, nombres, disponible=False)

    def suma(campo: str) -> float | None:
        valores = [getattr(marcas[n], campo) for n in presentes]
        return round(sum(valores), 2) if valores else None

    return PactoComparAgregado(
        ytd_comparable_anio_anterior=suma("ytd_comparable_anio_anterior"),
        ytd_actual=suma("ytd_actual"),
        marcas_incluidas=nombres,
        disponible=True,
    )


def parse_compar_octubre_2025(path: str | Path) -> list[ClienteCompar]:
    """Hoja 'LISTADO CLIENTES'. Compara YTD 2024 vs YTD 2025 (corte 16 octubre)."""
    df = pd.read_excel(path, sheet_name="LISTADO CLIENTES", header=0)

    # Mapa: nombre_marca -> (col_2024_completo, col_ytd24, col_ytd25, col_evol, col_oportunidad|None)
    marca_cols = {
        "avene": ("AVENE 2024", "AVENE YTD 24", "AVENE YTD 25", "EVOL AVENE", "OPORTUNIDAD AVENE"),
        "avene_sin_solar": ("AVENE SIN SOLAR 2024", "AVENE SIN SOLAR YTD 24", "AVENE SIN SOLAR YTD 25", "EVOL AVENE SIN SOLAR", None),
        "avene_solar": ("AVENE SOLAR 2024", "AVENE SOLAR YTD 24", "AVENE SOLAR YTD 25", "EVOL AVENE SOLAR", None),
        "ducray": ("DUCRAY 2024", "DUCRAY YTD 24", "DUCRAY YTD 25", "EVOL DUCRAY", "OPORTUNIDAD DUCRAY"),
        "aderma": ("A-DERMA 2024", "A-DERMAYTD 24", "A-DERMAYTD 25", "EVOL  ADERMA", "OPORTUNIDAD ADERMA"),
        "dexeryl": ("DEXERYL 2024", "DEXERYL YTD 24", "DEXERYL YTD 25", "EVOL DEXERYL", "OPORTUNIDAD DEXERYL"),
        "furterer": ("FURTERER 2024", "FURTERER YTD 24", "FURTERER YTD 25", "EVOL FURTERER", "OPORTUNIDAD RENE FURTERER"),
        "klorane": ("KLORANE 2024", "KLORANE YTD 24", "KLORANE YTD 25", "EVOL KLORANE", "OPORTUNIDAD KLORANE"),
        "hermesetas": ("HERMESETAS 2024", "HERMESETAS YTD 24", "HERMESETAS YTD 25", None, None),
        "cysticlean": ("CYSTICLEAN 2024", "CYSTICLEAN YTD 24", "CYSTICLEAN YTD 25", None, None),
    }

    clientes = []
    for _, row in df.iterrows():
        pos_id = str(row.get("POS", "")).strip()
        if pos_id.lower() == "nan":
            pos_id = ""  # sin código POS -- no descartar, la identidad real es dirección+CP+población (spec sección 7)
        lob_code = str(row.get("LOB", "")).strip()
        direccion = str(row.get("DIRECCION", "")).strip()
        if not pos_id and not lob_code and not direccion:
            continue  # fila realmente vacía, sin ningún identificador posible

        marcas: dict[str, MedidaMarcaCompar] = {}
        for nombre, (c_ant, c_ytd_ant, c_ytd_act, c_evol, c_op) in marca_cols.items():
            v_ant = _num(row.get(c_ant))
            v_ytd_ant = _num(row.get(c_ytd_ant))
            v_ytd_act = _num(row.get(c_ytd_act))
            v_evol = _num(row.get(c_evol)) if c_evol else None
            oportunidad = bool(c_op and isinstance(row.get(c_op), str) and row.get(c_op).strip())
            estado = "OK" if any(v is not None for v in (v_ant, v_ytd_ant, v_ytd_act)) else "ND"
            marcas[nombre] = MedidaMarcaCompar(v_ant, v_ytd_ant, v_ytd_act, v_evol, oportunidad, estado)

        cliente = ClienteCompar(
            fecha_referencia="OCT_2025",
            coach=str(row.get("COACH", "")),
            zona=None,
            lob_code=lob_code,
            pos_id=pos_id,
            nombre_cliente=str(row.get("NOMBRE CLIENTE", "")),
            direccion=str(row.get("DIRECCION", "")),
            codigo_postal=str(row.get("CP", "")),
            provincia=str(row.get("PROVINCIA", "")),
            poblacion=str(row.get("POBLACION", "")),
            identidad_fisica_id=identidad_fisica_id(str(row.get("DIRECCION", "")), str(row.get("CP", "")), str(row.get("POBLACION", ""))),
            marcas=marcas,
        )
        cliente.pacto_ada = _pacto(marcas, ["avene", "ducray", "aderma"])
        cliente.pacto_dexeryl = _pacto(marcas, ["dexeryl"])
        cliente.pacto_kf = _pacto(marcas, ["furterer", "klorane", "hermesetas", "cysticlean"])
        clientes.append(cliente)

    return clientes


def parse_compar_junio_2026(path: str | Path) -> list[ClienteCompar]:
    """Hoja 'INFORME DE VENTAS JUNIO 2026'. Compara YTD 2025 vs YTD 2026 (mismo corte).

    No trae datos de Furterer/Klorane/Hermesetas/Cysticlean para clientes en esta hoja
    (a diferencia del COMPAR de octubre) -- el Pacto KF se marca como no disponible, nunca como 0.
    """
    df = pd.read_excel(path, sheet_name="INFORME DE VENTAS JUNIO 2026", header=1)

    marca_cols = {
        "avene": ("AVENE 2025", "AVENE YTD 25", "AVENE YTD 26", "EVOL AVENE ", "OPORTUNIDAD AVENE"),
        "avene_sin_solar": ("AVENE 2025.1", "AVENE YTD 25.1", "AVENE YTD 26.1", "EVOL AVENE .1", "OPORTUNIDAD SIN SOLAR"),
        "avene_solar": ("AVENE 2025.2", "AVENE YTD 25.2", "AVENE YTD 26.2", "EVOL AVENE .2", "OPORTUNIDAD SOLAR"),
        "ducray": ("DUCRAY 2025", "DUCRAY YTD 25", "DUCRAY YTD 26", "EVOL DUCRAY", "OPORTUNIDAD DUCRAY"),
        "aderma": ("ADERMA 2025", "ADERMA YTD 25", "ADERMA YTD 26", "EVOL ADERMA", "OPORTUNIDAD ADERMA"),
        "dexeryl": ("DEXERYL 2025", "DEXERYL YTD 25", "DEXERYL YTD 26", "EVOL DEXERYL", "OPORTUNIDAD DEXERYL"),
    }

    clientes = []
    for _, row in df.iterrows():
        pos_id = str(row.get("LOB", "")).strip()  # esta hoja no trae columna POS (C0xxxxx), solo LOB numérico
        if not pos_id or pos_id.lower() == "nan":
            continue

        marcas: dict[str, MedidaMarcaCompar] = {}
        for nombre, (c_ant, c_ytd_ant, c_ytd_act, c_evol, c_op) in marca_cols.items():
            v_ant = _num(row.get(c_ant))
            v_ytd_ant = _num(row.get(c_ytd_ant))
            v_ytd_act = _num(row.get(c_ytd_act))
            v_evol = _num(row.get(c_evol))
            oportunidad = bool(isinstance(row.get(c_op), str) and row.get(c_op).strip())
            estado = "OK" if any(v is not None for v in (v_ant, v_ytd_ant, v_ytd_act)) else "ND"
            marcas[nombre] = MedidaMarcaCompar(v_ant, v_ytd_ant, v_ytd_act, v_evol, oportunidad, estado)

        cliente = ClienteCompar(
            fecha_referencia="JUN_2026",
            coach=str(row.get("COACH", "")),
            zona=str(row.get("ZONA", "")),
            lob_code=pos_id,
            pos_id=pos_id,  # sin código POS (C0xxxxx) en esta hoja -- ver aviso más abajo
            nombre_cliente=str(row.get("NOMBRE CLIENTE", "")),
            direccion=str(row.get("Dirección", "")),
            codigo_postal=str(row.get("CP", "")),
            provincia=str(row.get("Provincia", "")),
            poblacion=str(row.get("Población", "")),
            identidad_fisica_id=identidad_fisica_id(str(row.get("Dirección", "")), str(row.get("CP", "")), str(row.get("Población", ""))),
            marcas=marcas,
        )
        cliente.pacto_ada = _pacto(marcas, ["avene", "ducray", "aderma"])
        cliente.pacto_dexeryl = _pacto(marcas, ["dexeryl"])
        cliente.pacto_kf = _pacto(marcas, [])  # no disponible en esta hoja -- ver docstring
        clientes.append(cliente)

    return clientes


if __name__ == "__main__":
    oct25 = parse_compar_octubre_2025("docs/lob_compar/COMPAR_16_OCTUBRE_2025.xlsx")
    jun26 = parse_compar_junio_2026("docs/lob_compar/COMPAR_JUNIO_2026.xlsx")
    print(f"COMPAR OCT_2025: {len(oct25)} clientes")
    print(f"COMPAR JUN_2026: {len(jun26)} clientes")

    # Cliente real de ejemplo, buscado en ambos por identidad física (dirección+CP+población)
    ejemplo_oct = next((c for c in oct25 if c.pos_id == "C000149"), None)
    if ejemplo_oct:
        print("\n--- OCT_2025: SANCHEZ SANTALO NEUS (C000149) ---")
        print("Pacto ADA:", ejemplo_oct.pacto_ada)
        print("Pacto DEXERYL:", ejemplo_oct.pacto_dexeryl)
        print("Pacto KF:", ejemplo_oct.pacto_kf)

    print("\n--- JUN_2026: primer cliente con Pacto ADA disponible ---")
    ejemplo_jun = next((c for c in jun26 if c.pacto_ada and c.pacto_ada.disponible), None)
    if ejemplo_jun:
        print(ejemplo_jun.nombre_cliente, "-", ejemplo_jun.identidad_fisica_id)
        print("Pacto ADA:", ejemplo_jun.pacto_ada)
        print("Pacto DEXERYL:", ejemplo_jun.pacto_dexeryl)
        print("Pacto KF (debe ser no disponible):", ejemplo_jun.pacto_kf)
