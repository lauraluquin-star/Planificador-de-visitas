from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.auth import crea_token, delegado_actual, verifica_passcode
from backend.db import get_session
from backend.models import Delegado

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    passcode: str


class LoginResponse(BaseModel):
    token: str
    nombre_lob: str
    es_admin: bool


@router.post("/login", response_model=LoginResponse)
def login(datos: LoginRequest, session: Session = Depends(get_session)):
    delegado = session.exec(select(Delegado).where(Delegado.email == datos.email)).first()
    if delegado is None or not verifica_passcode(datos.passcode, delegado.passcode_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email o código incorrecto")
    return LoginResponse(token=crea_token(delegado.id), nombre_lob=delegado.nombre_lob, es_admin=delegado.es_admin)


@router.get("/yo", response_model=LoginResponse)
def yo(delegado: Delegado = Depends(delegado_actual)):
    return LoginResponse(token="", nombre_lob=delegado.nombre_lob, es_admin=delegado.es_admin)
