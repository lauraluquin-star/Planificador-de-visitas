"""
Exporta la cartera consolidada de un delegado a JSON para la Vista de Grupo
(scripts/generar_vista_grupo.py). Reutiliza la serialización compartida con el backend real
(src/serializacion.py) para no tener dos copias de esa lógica.

Uso: python scripts/exportar_cartera_grupo.py ["NOMBRE DELEGADO"] [ruta_salida.json]
"""

from __future__ import annotations

import json
import sys

sys.path.insert(0, ".")

from src.engine.comparacion import cartera_delegado
from src.parsers.acuerdos_parser import objetivos_por_pos_id, parse_acuerdos
from src.parsers.lob_parser import parse_lob
from src.serializacion import fila_cliente


def main() -> None:
    delegado = sys.argv[1] if len(sys.argv) > 1 else "LAURA LUQUIN FRANQUET"
    salida = sys.argv[2] if len(sys.argv) > 2 else "/tmp/cartera_laura_consolidada.json"

    clientes = parse_lob("docs/lob_compar/Listado_LOB_03_08_26.csv")
    acuerdos = parse_acuerdos("docs/acuerdos_comerciales/Listado_Acuerdos_Comerciales_LIVE.csv")
    objetivos = objetivos_por_pos_id(acuerdos)
    cartera = cartera_delegado(clientes, delegado, consolidar=True, objetivos_por_pos=objetivos)

    data = [fila_cliente(r, i, objetivos) for i, r in enumerate(cartera)]
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"OK: {len(data)} farmacias consolidadas exportadas a {salida}")


if __name__ == "__main__":
    main()
