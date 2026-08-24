from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from backend.auth import delegado_actual
from backend.datos_compartidos import clientes_lob_actuales, objetivos_pacto_actuales
from backend.db import get_session
from backend.models import Delegado
from src.engine.comparacion import cartera_delegado
from src.serializacion import fila_cliente

router = APIRouter(prefix="/cartera", tags=["cartera"])


@router.get("")
def mi_cartera(delegado: Delegado = Depends(delegado_actual), session: Session = Depends(get_session)):
    clientes = clientes_lob_actuales(session)
    if not clientes:
        raise HTTPException(status_code=409, detail="Todavía no hay ningún LOB activo subido -- pide a un admin que suba uno.")

    objetivos = objetivos_pacto_actuales(session)
    resumenes = cartera_delegado(clientes, delegado.nombre_lob, consolidar=True, objetivos_por_pos=objetivos)
    return [fila_cliente(r, i, objetivos) for i, r in enumerate(resumenes)]
