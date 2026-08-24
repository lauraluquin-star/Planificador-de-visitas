"""
Crea (o actualiza el passcode de) un delegado en la base de datos del backend.

Uso:
  python scripts/crear_delegado.py "LAURA LUQUIN FRANQUET" laura@correo.com miPasscode --admin

El primer argumento debe coincidir EXACTO con la columna "Nombre Delegado" del LOB (mayúsculas
incluidas) -- es la clave por la que la cartera se filtra para ese delegado.
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, ".")

from sqlmodel import Session, select

from backend.auth import hash_passcode
from backend.db import engine, init_db
from backend.models import Delegado


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("nombre_lob", help='Debe coincidir exacto con "Nombre Delegado" en el LOB')
    parser.add_argument("email")
    parser.add_argument("passcode")
    parser.add_argument("--admin", action="store_true", help="Puede subir LOB/Acuerdos/Catálogo/hojas de pedido")
    args = parser.parse_args()

    init_db()
    with Session(engine) as session:
        existente = session.exec(select(Delegado).where(Delegado.email == args.email)).first()
        if existente:
            existente.nombre_lob = args.nombre_lob
            existente.passcode_hash = hash_passcode(args.passcode)
            existente.es_admin = args.admin
            session.add(existente)
            session.commit()
            print(f"Actualizado: {existente.email} (nombre_lob={existente.nombre_lob}, admin={existente.es_admin})")
        else:
            nuevo = Delegado(
                nombre_lob=args.nombre_lob,
                email=args.email,
                passcode_hash=hash_passcode(args.passcode),
                es_admin=args.admin,
            )
            session.add(nuevo)
            session.commit()
            print(f"Creado: {nuevo.email} (nombre_lob={nuevo.nombre_lob}, admin={nuevo.es_admin})")


if __name__ == "__main__":
    main()
