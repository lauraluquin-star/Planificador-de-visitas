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

from collections import defaultdict
from dataclasses import dataclass, field

from src.parsers.lob_parser import ClienteLOB, MARCAS_ADA, MedidaMarca, PactoAgregado


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
class PuntoVentaConsolidado:
    """Un punto de venta físico real (spec sección 7: identidad = dirección+CP+población), que en
    el LOB puede aparecer repartido en varios POS-Id. Se consolidan aquí ANTES de diagnosticar,
    porque sumarlos cambia el diagnóstico (un cliente puede parecer sano en un POS-Id y perdido en
    otro, cuando en realidad es una sola farmacia)."""

    identidad_fisica_id: str
    pos_ids: list[str]
    nombre_cliente: str
    direccion: str
    poblacion: str
    provincia: str
    grupo_compra: str | None
    delegado_nombre: str
    pacto_ada: PactoAgregado
    pacto_dexeryl: PactoAgregado
    marcas: dict[str, MedidaMarca]  # sumadas entre los POS-Id consolidados


def _suma_medida_marca(medidas: list[MedidaMarca]) -> MedidaMarca:
    ok = [m for m in medidas if m.estado == "OK"]
    if not ok:
        return MedidaMarca(None, None, None, None, None, estado="ND")

    def suma(campo: str) -> float | None:
        vals = [getattr(m, campo) for m in ok if getattr(m, campo) is not None]
        return round(sum(vals), 2) if vals else None

    return MedidaMarca(
        importe_neto_2025=suma("importe_neto_2025"),
        objetivo_2026_lob_referencia=suma("objetivo_2026_lob_referencia"),
        importe_neto_ytd1=suma("importe_neto_ytd1"),
        importe_neto_ytd=suma("importe_neto_ytd"),
        evol_ytd_pct=None,  # se recalcula a partir de los importes ya sumados, no se suman porcentajes
        estado="OK",
    )


def _suma_pacto_agregados(pactos: list[PactoAgregado]) -> PactoAgregado:
    def suma(campo: str) -> float | None:
        vals = [getattr(p, campo) for p in pactos if getattr(p, campo) is not None]
        return round(sum(vals), 2) if vals else None

    marcas_incluidas = pactos[0].marcas_incluidas if pactos else []
    return PactoAgregado(
        importe_neto_2025=suma("importe_neto_2025"),
        importe_neto_ytd1=suma("importe_neto_ytd1"),
        importe_neto_ytd=suma("importe_neto_ytd"),
        marcas_incluidas=marcas_incluidas,
    )


def consolida_por_identidad_fisica(clientes: list[ClienteLOB]) -> list[PuntoVentaConsolidado]:
    grupos: dict[str, list[ClienteLOB]] = defaultdict(list)
    for c in clientes:
        grupos[c.identidad_fisica_id].append(c)

    resultado = []
    for identidad, grupo in grupos.items():
        principal = max(grupo, key=lambda c: (c.pacto_ada.importe_neto_ytd or 0))
        todas_marcas = set()
        for c in grupo:
            todas_marcas.update(c.marcas.keys())
        marcas_sumadas = {m: _suma_medida_marca([c.marcas[m] for c in grupo if m in c.marcas]) for m in todas_marcas}

        resultado.append(
            PuntoVentaConsolidado(
                identidad_fisica_id=identidad,
                pos_ids=[c.pos_id for c in grupo],
                nombre_cliente=principal.nombre_cliente,
                direccion=principal.direccion,
                poblacion=principal.poblacion,
                provincia=principal.provincia,
                grupo_compra=principal.grupo_compra if principal.grupo_compra != "NO GRUPOS" else None,
                delegado_nombre=principal.delegado_nombre,
                pacto_ada=_suma_pacto_agregados([c.pacto_ada for c in grupo]),
                pacto_dexeryl=_suma_pacto_agregados([c.pacto_dexeryl for c in grupo]),
                marcas=marcas_sumadas,
            )
        )
    return resultado


@dataclass
class DiagnosticoPerdida:
    """Para clientes con YTD=0 real (no N/D) pero YTD-1>0: qué facturaba el año pasado y en qué
    marcas, para dimensionar exactamente lo que se está perdiendo (no solo el semáforo rojo)."""

    facturacion_perdida_ada: float
    facturacion_perdida_dexeryl: float
    por_marca: dict[str, float]  # marca -> importe_neto_ytd1 (lo que compraba)


@dataclass
class ResumenCliente:
    cliente: ClienteLOB | PuntoVentaConsolidado
    pacto_ada: EstadoPacto
    pacto_dexeryl: EstadoPacto
    es_cliente_perdido: bool  # YTD=0 real Y YTD-1>0 en ADA o Dexeryl -- no es "sin datos", es 0 real
    perdida: DiagnosticoPerdida | None = None


def _es_perdido(pacto_ada: EstadoPacto, pacto_dexeryl: EstadoPacto) -> bool:
    def cero_real_con_historico(p: EstadoPacto) -> bool:
        return p.ytd == 0 and p.ytd1 is not None and p.ytd1 > 0

    return cero_real_con_historico(pacto_ada) or cero_real_con_historico(pacto_dexeryl)


def _diagnostico_perdida(cliente: ClienteLOB | PuntoVentaConsolidado, pacto_ada: EstadoPacto, pacto_dexeryl: EstadoPacto) -> DiagnosticoPerdida:
    por_marca = {
        marca: medida.importe_neto_ytd1
        for marca, medida in cliente.marcas.items()
        if medida.estado == "OK" and medida.importe_neto_ytd1 and medida.importe_neto_ytd1 > 0
    }
    return DiagnosticoPerdida(
        facturacion_perdida_ada=pacto_ada.ytd1 or 0 if (pacto_ada.ytd == 0) else 0,
        facturacion_perdida_dexeryl=pacto_dexeryl.ytd1 or 0 if (pacto_dexeryl.ytd == 0) else 0,
        por_marca=dict(sorted(por_marca.items(), key=lambda kv: -kv[1])),
    )


def evalua_cliente(cliente: ClienteLOB | PuntoVentaConsolidado) -> ResumenCliente:
    pacto_ada = evalua_pacto(cliente.pacto_ada, "ADA")
    pacto_dexeryl = evalua_pacto(cliente.pacto_dexeryl, "DEXERYL")
    perdido = _es_perdido(pacto_ada, pacto_dexeryl)
    return ResumenCliente(
        cliente=cliente,
        pacto_ada=pacto_ada,
        pacto_dexeryl=pacto_dexeryl,
        es_cliente_perdido=perdido,
        perdida=_diagnostico_perdida(cliente, pacto_ada, pacto_dexeryl) if perdido else None,
    )


def cartera_delegado(clientes: list[ClienteLOB], delegado_nombre: str, consolidar: bool = True) -> list[ResumenCliente]:
    """Filtra la cartera de un delegado y evalúa cada punto de venta. Cruzar SIEMPRE por
    delegado_nombre, nunca por nombre_dnv (que es el jefe de área, no el delegado).

    consolidar=True (por defecto): agrupa antes por identidad física (dirección+CP+población),
    porque varios POS-Id del mismo delegado pueden ser en realidad la misma farmacia -- sumar
    cambia el diagnóstico, así que se consolida ANTES de clasificar, no después."""
    propios = [c for c in clientes if c.delegado_nombre == delegado_nombre]
    if consolidar:
        puntos = consolida_por_identidad_fisica(propios)
        return [evalua_cliente(p) for p in puntos]
    return [evalua_cliente(c) for c in propios]


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from src.parsers.lob_parser import parse_lob

    clientes = parse_lob("docs/lob_compar/Listado_LOB_03_08_26.csv")

    sin_consolidar = cartera_delegado(clientes, "LAURA LUQUIN FRANQUET", consolidar=False)
    cartera = cartera_delegado(clientes, "LAURA LUQUIN FRANQUET", consolidar=True)
    print(f"Sin consolidar: {len(sin_consolidar)} POS-Id  |  Consolidado por identidad física: {len(cartera)} farmacias reales")

    rojos = [r for r in cartera if r.pacto_ada.estado == "NEGATIVA"]
    print(f"Pacto ADA en rojo (evolución < -15%), consolidado: {len(rojos)}")

    perdidos = [r for r in cartera if r.es_cliente_perdido]
    print(f"\nClientes PERDIDOS reales (YTD=0 con histórico YTD-1>0): {len(perdidos)}")
    total_perdido_ada = sum(r.perdida.facturacion_perdida_ada for r in perdidos)
    total_perdido_dex = sum(r.perdida.facturacion_perdida_dexeryl for r in perdidos)
    print(f"Facturación ADA perdida total: {total_perdido_ada:.0f} € | Dexeryl: {total_perdido_dex:.0f} €")

    if perdidos:
        ejemplo = max(perdidos, key=lambda r: r.perdida.facturacion_perdida_ada + r.perdida.facturacion_perdida_dexeryl)
        print(f"\nEjemplo (mayor pérdida): {ejemplo.cliente.nombre_cliente} ({', '.join(ejemplo.cliente.pos_ids) if hasattr(ejemplo.cliente, 'pos_ids') else ejemplo.cliente.pos_id})")
        print(f"  Perdía {ejemplo.perdida.facturacion_perdida_ada:.0f} € de ADA al año, por marca: {ejemplo.perdida.por_marca}")
