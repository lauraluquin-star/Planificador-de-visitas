"""
Motor de propuesta de pedido (spec sección 11): dado un cliente y una gama con oportunidad o
gap real, sugiere UNIDADES de arranque para los productos héroe de esa gama.

Regla de dimensionado, confirmada por la delegada (25/08/2026) -- NUNCA "gap en euros ÷ precio"
(CLAUDE.md: "El pedido propuesto nunca se calcula solo para rellenar el gap en euros"):
  1. Si la gama tiene un tramo de descuento real con unidades numéricas (chuleta del ciclo,
     condiciones_pacto_ciclo3.json), se propone llegar al primer tramo (el más bajo/alcanzable),
     repartido a partes iguales entre los productos héroe de esa gama.
  2. Si no hay tramo numérico (condición en texto libre, o tramo combinado entre varias
     marcas/gamas que no se puede repartir con criterio), se proponen 3 unidades de cada
     producto héroe -- regla explícita de la delegada: "los productos héroe siempre son mínimo
     3 unidades".
  3. Los productos NO héroe nunca llevan cantidad propuesta (quedan en 0, editable) -- proponer
     solo se apoya en héroe/tramo real, nunca en rellenar huecos a ciegas.

Esto es una PROPUESTA de arranque, siempre editable -- no un pedido final ni un objetivo
mecánico. Cualquier condición compuesta (p.ej. "+4% extra si incluyes 3+3 de Anacaps") se
muestra como nota de texto, nunca se aplica automáticamente.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.parsers.catalogo_parser import Producto
from src.parsers.pedido_ciclo_parser import HojaPedido, ProductoPedido

UDS_MINIMO_HEROE = 3

# hoja de pedido (pedido_ciclo_parser) -> clave de condiciones_pacto_ciclo3.json, solo pares
# verificados leyendo ambos ficheros. "None" explícito = existe pero el tramo mezcla varias
# marcas/gamas y no se reparte automáticamente (se muestra como nota).
HOJA_A_CONDICION_PACTO: dict[str, str | None] = {
    "antiedad": "avene_antiedad_hyaluron_activ_procedure",
    "acne_cleanance": "avene_ducray_aderma_acne_cleanance_keracnyl",
    "acne_keracnyl": "avene_ducray_aderma_acne_cleanance_keracnyl",
    "dexeryl": "dexeryl_dexeclear",
    "avene_esenciales": "avene_cuidados_esenciales",
    "atopia": None,  # atopia_exomega_xeracalm_dexyane: tramo combinado Exomega+XeraCalm+Dexyane
    "solar": "avene_solar",
}


@dataclass
class LineaPropuesta:
    cn: str
    marca: str
    descripcion: str
    formato: str
    uds_sugeridas: int
    pvl: float | None
    importe: float | None


@dataclass
class PropuestaGama:
    hoja: str
    lineas: list[LineaPropuesta]
    total_uds_objetivo: int
    origen: str  # "tramo" | "minimo_heroe"
    nota: str


def _primer_tramo_uds(condicion: dict) -> tuple[int, str] | None:
    tramos = condicion.get("tramos")
    if not tramos:
        return None
    primero = tramos[0]
    uds = primero.get("uds_inmediato") or primero.get("uds")
    if not isinstance(uds, int):
        return None
    etiqueta = primero.get("nivel", f"{uds} uds")
    return uds, f"tramo {etiqueta}: {uds} uds -> {primero.get('descuento_pct', primero.get('total_pct', '?'))}% dto"


def pvl_por_cn(productos_tarifa: list[Producto]) -> dict[int, float | None]:
    return {p.cn: p.pvl for p in productos_tarifa if p.cn is not None}


def _reparte_entre_heroes(n_heroes: int, tramo: tuple[int, str] | None, combinado: bool) -> tuple[list[int], str, str]:
    """Núcleo del reparto -- devuelve (cantidades, origen, nota), independiente de si el héroe
    viene de una HojaPedido transcrita o directamente de la tarifa."""
    if tramo is not None:
        tramo_uds, nota_tramo = tramo
        base = tramo_uds // n_heroes
        resto = tramo_uds % n_heroes
        if base >= UDS_MINIMO_HEROE:
            cantidades = [base] * n_heroes
            cantidades[0] += resto
            return cantidades, "tramo", f"Repartido entre {n_heroes} héroe de la gama para llegar exactamente al {nota_tramo}."
        cantidades = [UDS_MINIMO_HEROE] * n_heroes
        nota = (
            f"El {nota_tramo} solo pide {tramo_uds} uds en total; con {n_heroes} héroe y el mínimo "
            f"de {UDS_MINIMO_HEROE} uds cada uno (regla de la delegada) ya se llega a {UDS_MINIMO_HEROE * n_heroes} uds, "
            "por encima del tramo -- manda el mínimo por héroe, no el tramo."
        )
        return cantidades, "minimo_heroe_supera_tramo", nota

    cantidades = [UDS_MINIMO_HEROE] * n_heroes
    if combinado:
        nota = "Tramo de esta gama combinado con otras marcas en la chuleta -- no se reparte automático. Mínimo de arranque: 3 uds por héroe."
    else:
        nota = "Sin tramo numérico claro en la chuleta para esta gama. Mínimo de arranque: 3 uds por héroe (regla de la delegada)."
    return cantidades, "minimo_heroe", nota


def propone_pedido_gama(hoja: HojaPedido, condiciones_pacto: dict, pvl_lookup: dict[int, float | None]) -> PropuestaGama:
    heroes = [p for p in hoja.productos if p.heroe]
    if not heroes:
        return PropuestaGama(
            hoja=hoja.clave, lineas=[], total_uds_objetivo=0, origen="sin_heroe",
            nota="Esta hoja no tiene ningún producto marcado como héroe en la transcripción -- no se propone cantidad automática.",
        )

    clave_condicion = HOJA_A_CONDICION_PACTO.get(hoja.clave)
    condicion = condiciones_pacto.get(clave_condicion) if clave_condicion else None
    tramo = _primer_tramo_uds(condicion) if condicion else None
    combinado = clave_condicion is None and hoja.clave in HOJA_A_CONDICION_PACTO
    cantidades, origen, nota = _reparte_entre_heroes(len(heroes), tramo, combinado)

    lineas = []
    for producto, uds in zip(heroes, cantidades):
        cn_num = int(producto.cn.split(".")[0]) if producto.cn.split(".")[0].isdigit() else None
        pvl = producto.precio_especial or (pvl_lookup.get(cn_num) if cn_num is not None else None)
        importe = round(pvl * uds, 2) if pvl is not None else None
        lineas.append(LineaPropuesta(
            cn=producto.cn, marca=producto.marca, descripcion=producto.descripcion, formato=producto.formato,
            uds_sugeridas=uds, pvl=pvl, importe=importe,
        ))

    return PropuestaGama(hoja=hoja.clave, lineas=lineas, total_uds_objetivo=sum(cantidades), origen=origen, nota=nota)


# Gamas de la tarifa completa (marca, "Nombre Gama España") -> clave de condiciones_pacto_ciclo3.json.
# Complementa a HOJA_A_CONDICION_PACTO para gamas que aún no tienen hoja de pedido transcrita a
# JSON, pero sí están completas en la tarifa (docs/catalogo/tarifa_ciclo_3_raw.tsv). Solo pares
# verificados por nombre real de gama.
TARIFA_GAMA_A_CONDICION_PACTO: dict[tuple[str, str], str] = {
    ("Ducray", "ANTICAIDA"): "ducray_anticaida",
    ("Avène", "CICALFATE"): "avene_cicalfate",
}


def propone_pedido_tarifa_gama(marca: str, gama: str, productos_tarifa: list[Producto], condiciones_pacto: dict) -> PropuestaGama:
    """Igual que propone_pedido_gama pero directamente desde la tarifa completa (358 productos,
    todas las gamas), para cuando aún no hay hoja de pedido transcrita para esa gama."""
    heroes = [p for p in productos_tarifa if p.marca == marca and p.gama == gama and p.es_heroe]
    clave = f"{marca}|{gama}"
    if not heroes:
        return PropuestaGama(
            hoja=clave, lineas=[], total_uds_objetivo=0, origen="sin_heroe",
            nota="Ningún producto héroe en esta gama según la tarifa -- no se propone cantidad automática.",
        )

    condicion_key = TARIFA_GAMA_A_CONDICION_PACTO.get((marca, gama))
    condicion = condiciones_pacto.get(condicion_key) if condicion_key else None
    tramo = _primer_tramo_uds(condicion) if condicion else None
    cantidades, origen, nota = _reparte_entre_heroes(len(heroes), tramo, combinado=False)

    lineas = [
        LineaPropuesta(
            cn=str(p.cn), marca=p.marca, descripcion=p.descripcion, formato=p.formato,
            uds_sugeridas=uds, pvl=p.pvl, importe=round(p.pvl * uds, 2) if p.pvl is not None else None,
        )
        for p, uds in zip(heroes, cantidades)
    ]
    return PropuestaGama(hoja=clave, lineas=lineas, total_uds_objetivo=sum(cantidades), origen=origen, nota=nota)


def _imprime(propuesta: PropuestaGama) -> None:
    print(f"\n=== {propuesta.hoja} ({propuesta.origen}) -- objetivo {propuesta.total_uds_objetivo} uds ===")
    print(" ", propuesta.nota)
    for l in propuesta.lineas:
        pvl_txt = f"{l.pvl:.2f}€" if l.pvl is not None else "PVL N/D"
        importe_txt = f"{l.importe:.2f}€" if l.importe is not None else "—"
        print(f"   {l.uds_sugeridas:2d}x {l.descripcion} ({l.formato}) [{pvl_txt}] = {importe_txt}")


if __name__ == "__main__":
    from src.parsers.catalogo_parser import parse_catalogo
    from src.parsers.pedido_ciclo_parser import parse_condiciones_pacto, parse_hojas_ciclo

    hojas = parse_hojas_ciclo("docs/ciclo3/hojas_pedido")
    condiciones = parse_condiciones_pacto("docs/ciclo3/condiciones_descuentos")
    productos_tarifa = parse_catalogo("docs/catalogo/tarifa_ciclo_3_raw.tsv")
    pvl_lookup = pvl_por_cn(productos_tarifa)

    for clave, hoja in hojas.items():
        _imprime(propone_pedido_gama(hoja, condiciones, pvl_lookup))

    print("\n--- Directo desde tarifa (gamas sin hoja transcrita) ---")
    _imprime(propone_pedido_tarifa_gama("Ducray", "ANTICAIDA", productos_tarifa, condiciones))
    _imprime(propone_pedido_tarifa_gama("Avène", "CICALFATE", productos_tarifa, condiciones))
