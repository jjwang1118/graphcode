from fastapi import FastAPI

from app.api import analyze, health

app = FastAPI(title="codegraph")
app.include_router(health.router)
app.include_router(analyze.router)
