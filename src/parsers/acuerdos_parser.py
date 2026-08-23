"""
Parser del Listado de Acuerdos Comerciales (LIVE, exportado del sistema de Pierre Fabre).

Es la fuente REAL del objetivo (CIFRA PACTADA) de Pacto ADA y Pacto Dexeryl por cliente y por
marca -- a diferencia de la Ficha Cliente 2026 (de la que solo tenemos 2 ejemplos), este listado
cubre toda la cartera activa del delegado. Verificado con el usuario: el % de crecimiento exigido
para fijar la CIFRA PACTADA depende de la facturación del cliente (tramos, no un único 15% fijo) --
por eso NUNCA se recalcula el objetivo a partir de una fórmula propia; se usa siempre la CIFRA
PACTADA tal cual viene de este fichero (spec sección 5/6: nunca inventar un objetivo de pacto).

Formato real del fichero (verificado sobre datos reales, no supuesto):
- UTF-8, separado por PUNTO Y COMA.
- Bug de origen: la celda de acciones (última columna) a veces trae un salto de línea real sin
  comillas ("Ver PDF Editar Mayoristas Borrar Mayoristas" + salto + "Anular Acuerdo"), lo que
  rompe cada uno de esos registros en dos líneas físicas de CSV. Se repara por bloques: cada
  registro real empieza con una fecha "DD/MM/AAAA;" al principio de línea -- cualquier línea que
  no empiece así es continuación de la anterior y se junta con ella antes de parsear con csv.

Reglas de negocio aplicadas:
- Solo Estado acuerdo == "Activo" cuenta como objetivo vigente. Verificado sobre datos reales: un
  cliente puede tener un acuerdo Activo y otro Inactivo con la MISMA cifra pactada (renovación con
  mismos números, distinta referencia/fecha) -- el Inactivo es histórico, se descarta siempre.
- Solo se usan las marcas de Pacto ADA (Avène+Ducray+A-Derma) y Pacto Dexeryl. Furterer/Klorane
  aparecen en algunos acuerdos (marcados TIPO PACTO=COACH) pero CLAUDE.md prohíbe usarlos para
  objetivos/gaps de ADA o Dexeryl -- se parsean por completitud pero se excluyen de los totales
  de pacto.
- Identificador de cruce con LOB: "Nº CLIENTE PF" = mismo POS-Id que usa el LOB (columna pos_id).
"""

from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

_LINEA_REGISTRO = re.compile(r"^\d{2}/\d{2}/\d{4};")

MARCAS_PACTO_ADA = ["AVENE", "DUCRAY", "A-DERMA"]
MARCA_PACTO_DEXERYL = "DEXERYL"
MARCAS_KF_EXCLUIDAS = ["FURTERER", "KLORANE"]  # nunca se usan para objetivos ADA/Dexeryl


def _to_eur(s: str) -> float | None:
    s = s.replace(".", "").replace(",", ".").replace("€", "").strip()
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _to_pct(s: str) -> float | None:
    s = s.replace("%", "").replace(",", ".").strip()
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


@dataclass
class AcuerdoComercial:
    fecha_creacion: str
    marca: str
    referencia: str
    pos_id: str  # "Nº CLIENTE PF" -- mismo identificador que ClienteLOB.pos_id
    lob_cliente: str
    nombre_cliente: str
    cifra_pactada: float | None  # objetivo anual real del pacto para esta marca
    semestre_1: float | None
    semestre_2: float | None
    dto_real_pct: float | None
    tipo_pacto: str
    total_descuento_pct: float | None
    estado_acuerdo: str  # "Activo" | "Inactivo"


def _repara_lineas(texto: str) -> list[str]:
    """Junta las líneas físicas partidas por el salto de línea sin comillas de la celda de
    acciones. Un registro real siempre empieza por 'DD/MM/AAAA;' -- lo que no empiece así es
    continuación del registro anterior."""
    lineas_crudas = texto.split("\n")
    registros: list[str] = []
    actual: str | None = None
    for linea in lineas_crudas[1:]:  # [0] es la cabecera, se trata aparte
        linea = linea.rstrip("\r")
        if linea == "":
            continue
        if _LINEA_REGISTRO.match(linea):
            if actual is not None:
                registros.append(actual)
            actual = linea
        elif actual is not None:
            actual = actual + " " + linea.strip()
    if actual is not None:
        registros.append(actual)
    return registros


def parse_acuerdos(path: str | Path) -> list[AcuerdoComercial]:
    with open(path, encoding="utf-8", newline="") as f:
        texto = f.read()

    registros = _repara_lineas(texto)
    filas = [next(csv.reader(io.StringIO(r), delimiter=";")) for r in registros]

    acuerdos = []
    for fila in filas:
        if len(fila) < 17:
            continue
        acuerdos.append(
            AcuerdoComercial(
                fecha_creacion=fila[0],
                marca=fila[2].strip(),
                referencia=fila[3],
                pos_id=fila[4].strip(),
                lob_cliente=fila[5],
                nombre_cliente=fila[6],
                cifra_pactada=_to_eur(fila[7]),
                semestre_1=_to_eur(fila[8]),
                semestre_2=_to_eur(fila[9]),
                dto_real_pct=_to_pct(fila[10]),
                tipo_pacto=fila[11],
                total_descuento_pct=_to_pct(fila[15]),
                estado_acuerdo=fila[16].strip(),
            )
        )
    return acuerdos


def objetivos_por_pos_id(acuerdos: list[AcuerdoComercial]) -> dict[str, dict]:
    """Devuelve {pos_id: {"ADA": objetivo_eur|None, "DEXERYL": objetivo_eur|None, "por_marca": {...}}}
    a partir SOLO de acuerdos Activo. Ignora Furterer/Klorane (nunca cuentan en objetivo ADA/Dexeryl)."""
    activos = [
        a
        for a in acuerdos
        if a.estado_acuerdo == "Activo" and a.marca in (MARCAS_PACTO_ADA + [MARCA_PACTO_DEXERYL]) and a.cifra_pactada is not None
    ]

    resultado: dict[str, dict] = defaultdict(lambda: {"ADA": None, "DEXERYL": None, "por_marca": {}})
    for a in activos:
        entrada = resultado[a.pos_id]
        entrada["por_marca"][a.marca] = a.cifra_pactada
        bucket = "ADA" if a.marca in MARCAS_PACTO_ADA else "DEXERYL"
        entrada[bucket] = round((entrada[bucket] or 0) + a.cifra_pactada, 2)
    return dict(resultado)


if __name__ == "__main__":
    import sys

    ruta = sys.argv[1] if len(sys.argv) > 1 else "docs/acuerdos_comerciales/Listado_Acuerdos_Comerciales_LIVE.csv"
    acuerdos = parse_acuerdos(ruta)
    print(f"Acuerdos parseados: {len(acuerdos)}")

    activos = [a for a in acuerdos if a.estado_acuerdo == "Activo"]
    print(f"Activos: {len(activos)}  |  Inactivos: {len(acuerdos) - len(activos)}")

    objetivos = objetivos_por_pos_id(acuerdos)
    print(f"Clientes (pos_id) con objetivo de pacto vigente: {len(objetivos)}")

    ejemplo_pos = next(iter(objetivos))
    print(f"\nEjemplo real ({ejemplo_pos}): {objetivos[ejemplo_pos]}")
