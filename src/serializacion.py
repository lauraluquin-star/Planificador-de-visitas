"""
Serialización de ResumenCliente a un dict JSON-friendly, compartida entre el script que genera la
Vista de Grupo como artefacto (scripts/exportar_cartera_grupo.py) y el backend real (backend/routers).
Una sola función, para no tener dos copias de esta lógica que puedan divergir.
"""

from __future__ import annotations

from src.engine.comparacion import ResumenCliente, PuntoVentaConsolidado, pos_ids_vivos_de
from src.parsers.lob_parser import MARCAS_ADA

MARCAS_EXPORT = MARCAS_ADA + ["dexeryl"]
NOMBRE_MARCA = {
    "avene_sin_solar": "Avène (sin solar)",
    "avene_solar": "Avène Solar",
    "ducray": "Ducray",
    "aderma": "A-Derma",
    "dexeryl": "Dexeryl",
}

# La marca "AVENE" del Listado de Acuerdos Comerciales es Avène SIN solar (confirmado por la
# usuaria, delegada real) -- Avène Solar no entra en ese objetivo. Ver también nota de
# src/parsers/lob_parser.py sobre MARCAS_ADA: sigue pendiente decidir si además debe excluirse de
# la propia facturación de Pacto ADA usada para evolución/gap, o si solo el objetivo pactado excluye
# solar mientras la evolución del pacto sí la incluye -- no cambiar esa pieza sin confirmarlo.
MARCA_COMERCIAL_A_CLAVES_LOB = {
    "AVENE": ["avene_sin_solar"],
    "DUCRAY": ["ducray"],
    "A-DERMA": ["aderma"],
    "DEXERYL": ["dexeryl"],
}

# Clientes con captura real de Veeva confirmada (ver docs/ejemplos_cliente/veeva_*.json). Para el
# resto, la ficha debe decir explícitamente que no hay datos Veeva -- nunca inventar oportunidades.
# TODO: en cuanto backend/models.VeevaCaptura tenga filas CONFIRMADA reales, sustituir este set fijo
# por una consulta a la base de datos (delegado sube Veeva -> deja de ser "sin captura").
POS_IDS_CON_VEEVA = {"C006969"}


def _objetivo_por_marca_comercial(pos_ids_vivos: list[str], objetivos_por_pos: dict[str, dict] | None) -> dict:
    resultado = {}
    for marca_comercial in MARCA_COMERCIAL_A_CLAVES_LOB:
        valores = [
            objetivos_por_pos[p]["por_marca"][marca_comercial]
            for p in pos_ids_vivos
            if objetivos_por_pos and p in objetivos_por_pos and marca_comercial in objetivos_por_pos[p]["por_marca"]
        ]
        resultado[marca_comercial] = round(sum(valores), 2) if valores else None
    return resultado


def fila_cliente(resumen: ResumenCliente, idx: int, objetivos_por_pos: dict[str, dict] | None) -> dict:
    c = resumen.cliente
    if isinstance(c, PuntoVentaConsolidado):
        pos_ids_vivos = pos_ids_vivos_de(c.pos_ids, c.ytd_pacto_por_pos)
    else:
        pos_ids_vivos = [c.pos_id]
    marcas = {}
    for m in MARCAS_EXPORT:
        medida = c.marcas.get(m)
        if medida and medida.estado == "OK":
            marcas[m] = {"nombre": NOMBRE_MARCA[m], "ytd1": medida.importe_neto_ytd1, "ytd": medida.importe_neto_ytd}
        else:
            marcas[m] = {"nombre": NOMBRE_MARCA[m], "ytd1": None, "ytd": None}

    return {
        "id": idx,
        "pos_ids": c.pos_ids,
        "nombre": c.nombre_cliente,
        "direccion": c.direccion,
        "poblacion": c.poblacion,
        "provincia": c.provincia,
        "grupo": c.grupo_compra,
        "n_pos": len(c.pos_ids),
        "tiene_veeva": any(p in POS_IDS_CON_VEEVA for p in c.pos_ids),
        "objetivo_por_marca": _objetivo_por_marca_comercial(pos_ids_vivos, objetivos_por_pos),
        "ada_ytd": resumen.pacto_ada.ytd,
        "ada_ytd1": resumen.pacto_ada.ytd1,
        "ada_evol": resumen.pacto_ada.evolucion_pct,
        "ada_estado": resumen.pacto_ada.estado,
        "ada_objetivo": resumen.pacto_ada.objetivo,
        "ada_pct_cumplimiento": resumen.pacto_ada.pct_cumplimiento,
        "ada_gap": resumen.pacto_ada.gap,
        "dex_ytd": resumen.pacto_dexeryl.ytd,
        "dex_ytd1": resumen.pacto_dexeryl.ytd1,
        "dex_evol": resumen.pacto_dexeryl.evolucion_pct,
        "dex_estado": resumen.pacto_dexeryl.estado,
        "dex_objetivo": resumen.pacto_dexeryl.objetivo,
        "dex_pct_cumplimiento": resumen.pacto_dexeryl.pct_cumplimiento,
        "dex_gap": resumen.pacto_dexeryl.gap,
        "perdido_ada": resumen.perdida_ada is not None,
        "perdido_dex": resumen.perdida_dexeryl is not None,
        "perdida_ada_valor": resumen.perdida_ada.facturacion_perdida if resumen.perdida_ada else 0,
        "perdida_dex_valor": resumen.perdida_dexeryl.facturacion_perdida if resumen.perdida_dexeryl else 0,
        "perdida_ada_marcas": (
            [{"marca": NOMBRE_MARCA[m], "valor": v} for m, v in resumen.perdida_ada.por_marca.items()]
            if resumen.perdida_ada
            else []
        ),
        "marcas": marcas,
    }
