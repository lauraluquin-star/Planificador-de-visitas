"""
Parser de las hojas de pedido y condiciones de pacto del ciclo (docs/ciclo3/).

Las hojas de pedido y las condiciones son documentos muy visuales (PDF con fotos, tablas de
condiciones a mano en las chuletas) -- por eso ya se transcribieron a mano a JSON en sesiones
anteriores (catalogo_ciclo3_completo.json, atopia_solar_extraidos.json,
condiciones_pacto_ciclo3.json, condiciones_campana_ciclo3.json). Este módulo solo estructura
esos JSON ya transcritos; no vuelve a leer los PDF.

Cuando llegue un ciclo nuevo (p.ej. ciclo 4), la delegada trae los PDF nuevos, se transcriben
igual a JSON en docs/ciclo{N}/, y este parser se apunta a la carpeta del ciclo vigente --
diseñado para no tocar código al cambiar de ciclo (CLAUDE.md: "documentos de ciclo... cargables
como datos de configuración, no hardcodeados").
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProductoPedido:
    cn: str  # tal cual aparece en la hoja -- puede llevar sufijo (".P", ".9"...), no se recorta
    marca: str
    gama: str
    descripcion: str
    formato: str
    heroe: bool
    novedad: bool
    precio_especial: float | None
    hoja: str  # clave de la hoja de origen (antiedad, acne_cleanance, atopia...)


@dataclass
class HojaPedido:
    clave: str
    marca: str
    gama: str
    productos: list[ProductoPedido]
    condiciones_campana: list[str] = field(default_factory=list)


def _productos_de_bloque(clave: str, marca: str, gama: str, bloque: list[dict]) -> list[ProductoPedido]:
    return [
        ProductoPedido(
            cn=str(p["cn"]),
            marca=p.get("marca", marca),
            gama=p.get("gama", gama),
            descripcion=p["descripcion"],
            formato=p.get("formato", ""),
            heroe=bool(p.get("heroe", False)),
            novedad=bool(p.get("novedad", False)),
            precio_especial=p.get("precio_especial"),
            hoja=clave,
        )
        for p in bloque
    ]


def parse_hojas_ciclo(carpeta: str | Path) -> dict[str, HojaPedido]:
    carpeta = Path(carpeta)
    hojas: dict[str, HojaPedido] = {}

    completo = json.loads((carpeta / "catalogo_ciclo3_completo.json").read_text(encoding="utf-8"))
    claves_bloques = [k for k in completo if not k.startswith("_") and k != "hojas_incluidas"]
    for clave in claves_bloques:
        bloque = completo[clave]
        hojas[clave] = HojaPedido(
            clave=clave,
            marca=bloque["marca"],
            gama=bloque["gama"],
            productos=_productos_de_bloque(clave, bloque["marca"], bloque["gama"], bloque["productos"]),
            condiciones_campana=bloque.get("condiciones", []),
        )

    atopia_solar = json.loads((carpeta / "atopia_solar_extraidos.json").read_text(encoding="utf-8"))
    for clave in ("atopia", "solar"):
        bloque = atopia_solar[clave]
        productos = _productos_de_bloque(clave, "", "", bloque["productos"])
        hojas[clave] = HojaPedido(clave=clave, marca="", gama=clave.capitalize(), productos=productos)

    return hojas


def parse_condiciones_pacto(carpeta: str | Path) -> dict:
    carpeta = Path(carpeta)
    return json.loads((carpeta / "condiciones_pacto_ciclo3.json").read_text(encoding="utf-8"))


def parse_condiciones_campana(carpeta: str | Path) -> dict:
    carpeta = Path(carpeta)
    return json.loads((carpeta / "condiciones_campana_ciclo3.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    hojas = parse_hojas_ciclo("docs/ciclo3/hojas_pedido")
    for clave, h in hojas.items():
        heroes = [p for p in h.productos if p.heroe]
        print(f"{clave:16s} {h.marca:8s} | {h.gama[:40]:40s} | {len(h.productos):3d} productos, {len(heroes)} héroe")
