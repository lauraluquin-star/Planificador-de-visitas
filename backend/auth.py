"""
Autenticación mínima por delegado (spec: cada delegado ve solo su cartera). Nada de SSO/empresa
todavía -- login por email + passcode, token JWT de sesión. Suficiente para arrancar; si Pierre
Fabre exige SSO corporativo más adelante, se sustituye esta pieza sin tocar el resto.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from backend.db import get_session
from backend.models import Delegado

# En producción esto debe venir de una variable de entorno real, nunca hardcoded ni commiteado.
JWT_SECRET = os.environ.get("SVP_JWT_SECRET", "dev-secret-cambiar-en-produccion")
JWT_ALGORITHM = "HS256"
JWT_EXP_HOURS = 24 * 14

bearer_scheme = HTTPBearer()


def hash_passcode(passcode: str) -> str:
    return bcrypt.hashpw(passcode.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verifica_passcode(passcode: str, passcode_hash: str) -> bool:
    return bcrypt.checkpw(passcode.encode("utf-8"), passcode_hash.encode("utf-8"))


def crea_token(delegado_id: int) -> str:
    payload = {"delegado_id": delegado_id, "exp": datetime.utcnow() + timedelta(hours=JWT_EXP_HOURS)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def delegado_actual(
    credenciales: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: Session = Depends(get_session),
) -> Delegado:
    try:
        payload = jwt.decode(credenciales.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o caducado")

    delegado = session.get(Delegado, payload.get("delegado_id"))
    if delegado is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Delegado no encontrado")
    return delegado


def requiere_admin(delegado: Delegado = Depends(delegado_actual)) -> Delegado:
    if not delegado.es_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo un administrador puede hacer esto")
    return delegado
