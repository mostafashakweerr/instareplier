import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from database import init_db
from routes.api import router as api_router
from routes.dashboard import router as dashboard_router
from routes.webhook import router as webhook_router

app = FastAPI(title="InstaReply", version="1.0.0")

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Routers
app.include_router(dashboard_router)
app.include_router(webhook_router)
app.include_router(api_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.on_event("startup")
def startup():
    init_db()
    logging.getLogger("main").info("Database initialised ✓")
