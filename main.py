"""Servico de IA (FastAPI) do app Marvel: Jarvis + narrador de batalha."""

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import akinator, battle, jarvis

load_dotenv()

app = FastAPI(
    title="Marvel RPG - Servico de IA",
    description="Jarvis, narrador de batalha e Akinator com LangChain + Gemini.",
    version="1.0.0",
)

_origins_env: str = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS: list[str] = [o.strip() for o in _origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(jarvis.router)
app.include_router(battle.router)
app.include_router(akinator.router)


@app.get("/health", tags=["infra"])
def health() -> dict[str, str]:
    """Healthcheck sem autenticacao, usado pelo Render."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )
