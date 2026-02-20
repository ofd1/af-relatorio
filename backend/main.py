"""
FastAPI principal — orquestra o sistema de automação financeira.

Inclui autenticação via cookie httponly, CORS, e monta todos os routers.
"""

from __future__ import annotations

import logging
import time

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt, JWTError

from backend.config import get_settings
from backend.sheets.sheets_client import SheetsClient

from backend.routers import upload, dashboard, depara, export, companies

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes de autenticação
# ---------------------------------------------------------------------------
_JWT_SECRET = "af-relatorio-secret-key"
_JWT_ALGORITHM = "HS256"
_TOKEN_EXPIRE_SECONDS = 60 * 60 * 24  # 24 horas
_COOKIE_NAME = "af_session"

# ---------------------------------------------------------------------------
# Lifespan — inicializa SheetsClient uma vez
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Inicializa recursos compartilhados no startup."""
    settings = get_settings()
    try:
        client = SheetsClient(
            credentials_json=settings.google_credentials_json,
            spreadsheet_id=settings.sheets_id_default,
        )
        application.state.sheets_client = client
        logger.info("SheetsClient inicializado com sucesso.")
    except Exception as exc:
        logger.error("Falha ao inicializar SheetsClient: %s", exc)
        application.state.sheets_client = None
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AF Relatório — API",
    description="API de automação financeira: upload de balancetes, DRE, BP, DFC.",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
settings = get_settings()
_origins = [settings.frontend_url]
if "localhost" not in settings.frontend_url:
    _origins.append("http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@app.post("/api/login")
async def login(body: dict, response: Response):
    """Autentica com senha e retorna cookie httponly."""
    password = body.get("password", "")
    if password != get_settings().app_password:
        raise HTTPException(status_code=401, detail="Senha incorreta")

    expires = int(time.time()) + _TOKEN_EXPIRE_SECONDS
    token = jwt.encode(
        {"sub": "user", "exp": expires},
        _JWT_SECRET,
        algorithm=_JWT_ALGORITHM,
    )

    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=_TOKEN_EXPIRE_SECONDS,
        samesite="lax",
        secure=False,  # True em produção com HTTPS
    )

    return {"token": "ok", "expires": expires}


# ---------------------------------------------------------------------------
# Middleware de autenticação
# ---------------------------------------------------------------------------


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Verifica cookie de sessão em todas as rotas /api/* exceto /api/login."""
    path = request.url.path

    # Rotas públicas
    if not path.startswith("/api/") or path == "/api/login":
        return await call_next(request)

    # Verifica cookie
    token = request.cookies.get(_COOKIE_NAME)
    if not token:
        return Response(
            content='{"detail":"Não autenticado"}',
            status_code=401,
            media_type="application/json",
        )

    try:
        jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
    except JWTError:
        return Response(
            content='{"detail":"Token inválido ou expirado"}',
            status_code=401,
            media_type="application/json",
        )

    return await call_next(request)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(upload.router)
app.include_router(dashboard.router)
app.include_router(depara.router)
app.include_router(export.router)
app.include_router(companies.router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {"status": "ok"}
