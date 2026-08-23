"""
Motor de comparación reutilizable: a partir de un ClienteLOB (o de varios clientes de una
cartera/grupo), calcula evolución y estado comercial.

Importante -- lo que este motor SÍ y NO puede calcular con solo el LOB:
- SÍ: evolución YTD vs YTD-1 (año anterior comparable), disponible para TODOS los clientes del LOB.
- NO: % cumplimiento real de objetivo, porque el objetivo del Pacto sale de la Ficha Cliente 2026
  (sección 6 de la spec), que solo tenemos para 2 clientes de ejemplo. Para el resto de la cartera,
  el "estado" se basa solo en evolución -- se marca explícitamente `objetivo_disponible=False` para
  no fingir que hay más precisión de la que hay (spec sección 13: no inventar precisión falsa).

Clasificación de tendencia (spec sección 14), simplificada a lo calculable sin objetivo:
  🟢 POSITIVA: evolución >= 0%
  🟡 NEGATIVA CONTROLADA: evolución entre -15% y 0%
  🔴 NEGATIVA: evolución < -15%
  ⚪ SIN DATOS: no hay YTD o YTD-1 (ND)
"""

from __future__ import annotations

from dataclasses import dataclass

from src.parsers.lob_parser import ClienteLOB, PactoAgregado


@dataclass
class EstadoPacto:
    tipo: str  # "ADA" | "DEXERYL" | "KF"
    ytd: float | None
    ytd1: float | None
    evolucion_pct: float | None
    estado: str  # "POSITIVA" | "NEGATIVA_CONTROLADA" | "NEGATIVA" | "SIN_DATOS"
    semaforo: str  # emoji
    objetivo_disponible: bool = False


def _clasifica(evolucion_pct: float | None) -> tuple[str, str]:
    if evolucion_pct is None:
        return "SIN_DATOS", "⚪"
    if evolucion_pct >= 0:
        return "POSITIVA", "🟢"
    if evolucion_pct >= -15:
        return "NEGATIVA_CONTROLADA", "🟡"
    return "NEGATIVA", "🔴"


def evalua_pacto(pacto: PactoAgregado | None, tipo: str) -> EstadoPacto:
    if pacto is None or pacto.importe_neto_ytd is None or pacto.importe_neto_ytd1 is None:
        return EstadoPacto(tipo=tipo, ytd=None, ytd1=None, evolucion_pct=None, estado="SIN_DATOS", semaforo="⚪")

    ytd, ytd1 = pacto.importe_neto_ytd, pacto.importe_neto_ytd1
    if ytd1 == 0:
        evolucion = None if ytd == 0 else 100.0  # de 0 a algo: no se puede expresar como % de crecimiento real
    else:
        evolucion = round((ytd - ytd1) / ytd1 * 100, 1)

    estado, semaforo = _clasifica(evolucion)
    return EstadoPacto(tipo=tipo, ytd=ytd, ytd1=ytd1, evolucion_pct=evolucion, estado=estado, semaforo=semaforo)


@dataclass
class ResumenCliente:
    cliente: ClienteLOB
    pacto_ada: EstadoPacto
    pacto_dexeryl: EstadoPacto


def evalua_cliente(cliente: ClienteLOB) -> ResumenCliente:
    return ResumenCliente(
        cliente=cliente,
        pacto_ada=evalua_pacto(cliente.pacto_ada, "ADA"),
        pacto_dexeryl=evalua_pacto(cliente.pacto_dexeryl, "DEXERYL"),
    )


def cartera_delegado(clientes: list[ClienteLOB], delegado_nombre: str) -> list[ResumenCliente]:
    """Filtra la cartera de un delegado y evalúa cada cliente. Cruzar SIEMPRE por delegado_nombre,
    nunca por nombre_dnv (que es el jefe de área, no el delegado -- ver docstring de lob_parser)."""
    propios = [c for c in clientes if c.delegado_nombre == delegado_nombre]
    return [evalua_cliente(c) for c in propios]


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from src.parsers.lob_parser import parse_lob

    clientes = parse_lob("docs/lob_compar/Listado_LOB_03_08_26.csv")
    cartera = cartera_delegado(clientes, "LAURA LUQUIN FRANQUET")
    print(f"Cartera: {len(cartera)} clientes")

    rojos = [r for r in cartera if r.pacto_ada.estado == "NEGATIVA"]
    print(f"Pacto ADA en rojo (evolución < -15%): {len(rojos)}")

    font_soler = next((r for r in cartera if r.cliente.pos_id == "C006969"), None)
    if font_soler:
        print("\nEjemplo Font Soler Pilar:")
        print(" Pacto ADA:", font_soler.pacto_ada)
        print(" Pacto Dexeryl:", font_soler.pacto_dexeryl)
