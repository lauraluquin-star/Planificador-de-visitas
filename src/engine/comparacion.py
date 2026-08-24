"""
Motor de comparación reutilizable: a partir de un ClienteLOB (o de varios clientes de una
cartera/grupo), calcula evolución y estado comercial.

Lo que este motor puede calcular y de dónde sale:
- Evolución YTD vs YTD-1 (año anterior comparable): sale del LOB, disponible para TODOS los
  clientes.
- Objetivo real de Pacto ADA/Dexeryl (CIFRA PACTADA) y % de cumplimiento/gap: sale del Listado de
  Acuerdos Comerciales LIVE (src/parsers/acuerdos_parser.py), que cubre la cartera activa del
  delegado -- no de una fórmula propia. Verificado con el usuario: el % de crecimiento exigido para
  fijar la cifra pactada depende de la facturación de cada cliente (varía por tramos, no es un 15%
  fijo), así que el objetivo NUNCA se recalcula aquí -- se usa tal cual venga del listado, y si un
  cliente no tiene acuerdo Activo se marca `objetivo_disponible=False` en vez de inventar un número
  (spec sección 15-16: "Objetivo de pacto individual no disponible", nunca sustituir en silencio).

Clasificación de tendencia (spec sección 14), basada en evolución vs año anterior:
  🟢 POSITIVA: evolución >= 0%
  🟡 NEGATIVA CONTROLADA: evolución entre -15% y 0%
  🔴 NEGATIVA: evolución < -15%
  ⚪ SIN DATOS: no hay YTD o YTD-1 (ND)
% cumplimiento y gap respecto al objetivo se calculan aparte cuando hay acuerdo Activo, y se
muestran siempre junto a la evolución -- nunca uno solo (spec sección 3: "año anterior Y objetivo
del pacto, nunca una sola perspectiva"). No se usan todavía para el semáforo: ese sigue basado en
evolución, ya validado con el usuario sobre datos reales.
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
    objetivo: float | None = None  # CIFRA PACTADA real (Acuerdos Comerciales), None si no hay acuerdo Activo
    pct_cumplimiento: float | None = None  # ytd / objetivo * 100
    gap: float | None = None  # objetivo - ytd
    objetivo_disponible: bool = False


def _clasifica(evolucion_pct: float | None) -> tuple[str, str]:
    if evolucion_pct is None:
        return "SIN_DATOS", "⚪"
    if evolucion_pct >= 0:
        return "POSITIVA", "🟢"
    if evolucion_pct >= -15:
        return "NEGATIVA_CONTROLADA", "🟡"
    return "NEGATIVA", "🔴"


def evalua_pacto(pacto: PactoAgregado | None, tipo: str, objetivo: float | None = None) -> EstadoPacto:
    if pacto is None or pacto.importe_neto_ytd is None or pacto.importe_neto_ytd1 is None:
        return EstadoPacto(tipo=tipo, ytd=None, ytd1=None, evolucion_pct=None, estado="SIN_DATOS", semaforo="⚪")

    ytd, ytd1 = pacto.importe_neto_ytd, pacto.importe_neto_ytd1
    if ytd1 == 0:
        evolucion = None if ytd == 0 else 100.0  # de 0 a algo: no se puede expresar como % de crecimiento real
    else:
        evolucion = round((ytd - ytd1) / ytd1 * 100, 1)

    estado, semaforo = _clasifica(evolucion)

    pct_cumplimiento = round(ytd / objetivo * 100, 1) if objetivo else None
    gap = round(objetivo - ytd, 2) if objetivo is not None else None

    return EstadoPacto(
        tipo=tipo,
        ytd=ytd,
        ytd1=ytd1,
        evolucion_pct=evolucion,
        estado=estado,
        semaforo=semaforo,
        objetivo=objetivo,
        pct_cumplimiento=pct_cumplimiento,
        gap=gap,
        objetivo_disponible=objetivo is not None,
    )


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
    ytd_pacto_por_pos: dict[str, dict[str, float | None]]  # pos_id -> {"ADA": ytd, "DEXERYL": ytd} -- SIN consolidar, la cifra propia de cada POS-Id


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
                ytd_pacto_por_pos={
                    c.pos_id: {
                        "ADA": c.pacto_ada.importe_neto_ytd,
                        "DEXERYL": c.pacto_dexeryl.importe_neto_ytd if c.pacto_dexeryl else None,
                    }
                    for c in grupo
                },
            )
        )
    return resultado


@dataclass
class DiagnosticoPerdida:
    """Un pacto (ADA o Dexeryl) con YTD=0 real (no N/D) pero YTD-1>0: qué facturaba el año pasado
    y en qué marcas DE ESE PACTO, para dimensionar la pérdida sin mezclar el otro pacto -- CLAUDE.md:
    Pacto ADA y Pacto Dexeryl son independientes, nunca sumarlos ni mezclarlos, tampoco en este
    diagnóstico. Un cliente puede tener Dexeryl perdido con el Pacto ADA sano, o al revés."""

    tipo: str  # "ADA" | "DEXERYL"
    facturacion_perdida: float  # = ytd1 del pacto perdido
    por_marca: dict[str, float]  # solo las marcas de ESE pacto, marca -> importe_neto_ytd1


@dataclass
class ResumenCliente:
    cliente: ClienteLOB | PuntoVentaConsolidado
    pacto_ada: EstadoPacto
    pacto_dexeryl: EstadoPacto
    perdida_ada: DiagnosticoPerdida | None = None
    perdida_dexeryl: DiagnosticoPerdida | None = None

    @property
    def tiene_alguna_perdida(self) -> bool:
        return self.perdida_ada is not None or self.perdida_dexeryl is not None


def _cero_real_con_historico(p: EstadoPacto) -> bool:
    return p.ytd == 0 and p.ytd1 is not None and p.ytd1 > 0


def _diagnostico_perdida_pacto(cliente: ClienteLOB | PuntoVentaConsolidado, pacto: EstadoPacto, marcas_del_pacto: list[str]) -> DiagnosticoPerdida:
    por_marca = {
        marca: cliente.marcas[marca].importe_neto_ytd1
        for marca in marcas_del_pacto
        if marca in cliente.marcas
        and cliente.marcas[marca].estado == "OK"
        and cliente.marcas[marca].importe_neto_ytd1
        and cliente.marcas[marca].importe_neto_ytd1 > 0
    }
    return DiagnosticoPerdida(
        tipo=pacto.tipo,
        facturacion_perdida=pacto.ytd1 or 0,
        por_marca=dict(sorted(por_marca.items(), key=lambda kv: -kv[1])),
    )


def pos_ids_vivos_de(pos_ids: list[str], ytd_pacto_por_pos: dict[str, dict[str, float | None]]) -> list[str]:
    """Un pos_id está "vivo" si tiene actividad real (YTD != 0 y != None) en CUALQUIER pacto este
    año -- un cambio de titular mueve toda la relación a la vez, no un pacto sí y otro no, así que
    se decide una sola vez por pos_id y se aplica igual a ADA y a Dexeryl (ver _objetivo_consolidado)."""
    vivos = [
        p
        for p in pos_ids
        if any((ytd_pacto_por_pos.get(p, {}).get(b) or 0) != 0 for b in ("ADA", "DEXERYL"))
    ]
    return vivos or pos_ids  # si ninguno tiene actividad (cliente realmente perdido), no hay señal -- no se descarta nada


def _objetivo_consolidado(
    pos_ids: list[str],
    objetivos_por_pos: dict[str, dict] | None,
    bucket: str,
    pos_ids_vivos: list[str],
) -> float | None:
    """Suma el objetivo (CIFRA PACTADA) de los pos_ids del punto consolidado -- pero NO a ciegas.

    Caso real encontrado (verificado sobre 2 clientes de la cartera: FARMATEROS SL y MILLAN HOMEDES
    ELISEO JOSE): cuando una farmacia cambia de titular a mitad de ciclo, el POS-Id antiguo se queda
    con su propio acuerdo Activo en el sistema (mismas cifras, referencia distinta) aunque ya no
    facture nada -- toda la facturación real ya está en el POS-Id nuevo. Sumar el objetivo de ambos
    duplica el objetivo (se vio literalmente x2 en FARMATEROS). La facturación SÍ hay que sumarla
    (por eso se consolida), pero el objetivo solo debe contar una vez, del/de los POS-Id que siguen
    vivos (ver pos_ids_vivos_de) -- no del POS-Id dormido que dejó de facturar tras el cambio.
    """
    if not objetivos_por_pos:
        return None

    valores = [
        objetivos_por_pos[p][bucket] for p in pos_ids_vivos if p in objetivos_por_pos and objetivos_por_pos[p][bucket] is not None
    ]
    return round(sum(valores), 2) if valores else None


def evalua_cliente(
    cliente: ClienteLOB | PuntoVentaConsolidado,
    objetivos_por_pos: dict[str, dict] | None = None,
) -> ResumenCliente:
    """objetivos_por_pos: salida de acuerdos_parser.objetivos_por_pos_id() -- {pos_id: {"ADA":
    €|None, "DEXERYL": €|None}}. Si el cliente es un PuntoVentaConsolidado con varios pos_ids, se
    suman los objetivos de los pos_ids que facturan de verdad hoy (ver _objetivo_consolidado) --
    igual que se suma la facturación al consolidar, pero sin duplicar el objetivo de un POS-Id
    dormido por cambio de titular."""
    if isinstance(cliente, PuntoVentaConsolidado):
        pos_ids = cliente.pos_ids
        ytd_pacto_por_pos = cliente.ytd_pacto_por_pos
    else:
        pos_ids = [cliente.pos_id]
        ytd_pacto_por_pos = {
            cliente.pos_id: {
                "ADA": cliente.pacto_ada.importe_neto_ytd,
                "DEXERYL": cliente.pacto_dexeryl.importe_neto_ytd if cliente.pacto_dexeryl else None,
            }
        }
    pos_ids_vivos = pos_ids_vivos_de(pos_ids, ytd_pacto_por_pos)
    objetivo_ada = _objetivo_consolidado(pos_ids, objetivos_por_pos, "ADA", pos_ids_vivos)
    objetivo_dexeryl = _objetivo_consolidado(pos_ids, objetivos_por_pos, "DEXERYL", pos_ids_vivos)

    pacto_ada = evalua_pacto(cliente.pacto_ada, "ADA", objetivo_ada)
    pacto_dexeryl = evalua_pacto(cliente.pacto_dexeryl, "DEXERYL", objetivo_dexeryl)
    return ResumenCliente(
        cliente=cliente,
        pacto_ada=pacto_ada,
        pacto_dexeryl=pacto_dexeryl,
        perdida_ada=_diagnostico_perdida_pacto(cliente, pacto_ada, MARCAS_ADA) if _cero_real_con_historico(pacto_ada) else None,
        perdida_dexeryl=_diagnostico_perdida_pacto(cliente, pacto_dexeryl, ["dexeryl"]) if _cero_real_con_historico(pacto_dexeryl) else None,
    )


def cartera_delegado(
    clientes: list[ClienteLOB],
    delegado_nombre: str,
    consolidar: bool = True,
    objetivos_por_pos: dict[str, dict] | None = None,
) -> list[ResumenCliente]:
    """Filtra la cartera de un delegado y evalúa cada punto de venta. Cruzar SIEMPRE por
    delegado_nombre, nunca por nombre_dnv (que es el jefe de área, no el delegado).

    consolidar=True (por defecto): agrupa antes por identidad física (dirección+CP+población),
    porque varios POS-Id del mismo delegado pueden ser en realidad la misma farmacia -- sumar
    cambia el diagnóstico, así que se consolida ANTES de clasificar, no después.

    objetivos_por_pos: opcional, salida de acuerdos_parser.objetivos_por_pos_id() -- si se pasa,
    cada ResumenCliente lleva el objetivo real de pacto (CIFRA PACTADA) cuando exista un acuerdo
    Activo; si no, queda objetivo_disponible=False (nunca se inventa)."""
    propios = [c for c in clientes if c.delegado_nombre == delegado_nombre]
    if consolidar:
        puntos = consolida_por_identidad_fisica(propios)
        return [evalua_cliente(p, objetivos_por_pos) for p in puntos]
    return [evalua_cliente(c, objetivos_por_pos) for c in propios]


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from src.parsers.acuerdos_parser import parse_acuerdos, objetivos_por_pos_id
    from src.parsers.lob_parser import parse_lob

    clientes = parse_lob("docs/lob_compar/Listado_LOB_03_08_26.csv")
    acuerdos = parse_acuerdos("docs/acuerdos_comerciales/Listado_Acuerdos_Comerciales_LIVE.csv")
    objetivos = objetivos_por_pos_id(acuerdos)

    sin_consolidar = cartera_delegado(clientes, "LAURA LUQUIN FRANQUET", consolidar=False)
    cartera = cartera_delegado(clientes, "LAURA LUQUIN FRANQUET", consolidar=True, objetivos_por_pos=objetivos)
    print(f"Sin consolidar: {len(sin_consolidar)} POS-Id  |  Consolidado por identidad física: {len(cartera)} farmacias reales")

    con_objetivo = [r for r in cartera if r.pacto_ada.objetivo_disponible]
    print(f"Con objetivo de Pacto ADA vigente (acuerdo Activo): {len(con_objetivo)} de {len(cartera)}")

    ejemplo = max(con_objetivo, key=lambda r: r.pacto_ada.objetivo)
    print(f"\nEjemplo real -- {ejemplo.cliente.nombre_cliente}:")
    print(f"  Pacto ADA: objetivo {ejemplo.pacto_ada.objetivo:.0f}€, YTD {ejemplo.pacto_ada.ytd:.0f}€, "
          f"cumplimiento {ejemplo.pacto_ada.pct_cumplimiento}%, gap {ejemplo.pacto_ada.gap:.0f}€")
    if ejemplo.pacto_dexeryl.objetivo_disponible:
        print(f"  Pacto DEXERYL: objetivo {ejemplo.pacto_dexeryl.objetivo:.0f}€, YTD {ejemplo.pacto_dexeryl.ytd:.0f}€, "
              f"cumplimiento {ejemplo.pacto_dexeryl.pct_cumplimiento}%, gap {ejemplo.pacto_dexeryl.gap:.0f}€")

    rojos = [r for r in cartera if r.pacto_ada.estado == "NEGATIVA"]
    print(f"Pacto ADA en rojo (evolución < -15%), consolidado: {len(rojos)}")

    perdidos_ada = [r for r in cartera if r.perdida_ada]
    perdidos_dex = [r for r in cartera if r.perdida_dexeryl]
    print(f"\nPacto ADA perdido de verdad (YTD=0, YTD-1>0): {len(perdidos_ada)} clientes")
    print(f"Pacto DEXERYL perdido de verdad: {len(perdidos_dex)} clientes")
    print(f"Total ADA perdido: {sum(r.perdida_ada.facturacion_perdida for r in perdidos_ada):.0f} €")
    print(f"Total DEXERYL perdido: {sum(r.perdida_dexeryl.facturacion_perdida for r in perdidos_dex):.0f} €")

    if perdidos_ada:
        ejemplo = max(perdidos_ada, key=lambda r: r.perdida_ada.facturacion_perdida)
        print(f"\nMayor pérdida ADA: {ejemplo.cliente.nombre_cliente} -- {ejemplo.perdida_ada.facturacion_perdida:.0f} €, por marca: {ejemplo.perdida_ada.por_marca}")
