from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db import init_db
from backend.routers import admin_router, auth_router, cartera_router, visita_router

app = FastAPI(title="Smart Visit Planner API")

# Mientras no haya dominio de producción decidido, se permite cualquier origen -- el token JWT es
# lo que protege los datos, no el CORS. Ajustar cuando se decida dónde vive el frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


app.include_router(auth_router.router)
app.include_router(admin_router.router)
app.include_router(cartera_router.router)
app.include_router(visita_router.router)


@app.get("/salud")
def salud():
    return {"estado": "ok"}
