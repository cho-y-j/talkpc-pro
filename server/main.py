"""TalkPC Pro 백엔드 — FastAPI on Vercel + Neon Postgres."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from api import auth

app = FastAPI(
    title="TalkPC Pro API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 클라이언트는 PC 앱이라 좁힐 의미 적음
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)


@app.get("/")
def root():
    return {"service": "talkpc-pro", "status": "ok"}


@app.get("/health")
def health():
    return {"ok": True}


# Vercel serverless 진입점
handler = Mangum(app, lifespan="off")
