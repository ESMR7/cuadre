from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import bolsas, cuenta, dinero, sesiones, usuarios
from app.api.errores import registrar_manejadores
from app.config import obtener_configuracion

app = FastAPI(title="Cuadre")
registrar_manejadores(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=obtener_configuracion().lista_cors_origenes(),
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)
for modulo in (usuarios, sesiones, cuenta, dinero, bolsas):
    app.include_router(modulo.router)


@app.get("/health")
def health():
    return {"status": "ok"}
