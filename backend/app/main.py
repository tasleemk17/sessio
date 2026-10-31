import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .db import Base, engine
from .middleware import BodyLimit, SecurityHeaders
from .routers import auth, bookings, experts

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# httpx logs every request URL at INFO. Quiet, in case a URL ever carries a secret.
for noisy in ("httpx", "httpcore"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
log = logging.getLogger("sessio")


@asynccontextmanager
async def lifespan(_: FastAPI):
    problems = config.startup_problems()
    for problem in problems:
        log.error("Unsafe configuration: %s", problem) if config.PRODUCTION else log.warning("Dev setting: %s", problem)
    if config.PRODUCTION and problems:
        raise RuntimeError("Refusing to start in production: " + "; ".join(problems))
    if config.payment_mode() == "mock":
        log.warning("Payments are in DEMO mode: any booking can be confirmed without paying.")
    Base.metadata.create_all(engine)
    yield


# The interactive docs and the schema list every endpoint: handy on a laptop, needless on the internet
docs = None if config.PRODUCTION else "/docs"
app = FastAPI(title="Sessio", version="1.0.0", lifespan=lifespan, docs_url=docs, redoc_url=None, openapi_url=None if config.PRODUCTION else "/openapi.json")

# The one added last is the outermost. Size is checked closest to the app, so even a "too large" answer
# still carries the CORS and security headers.
app.add_middleware(BodyLimit)
app.add_middleware(SecurityHeaders)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=False,  # the token travels in a header, never a cookie, so cross-site pages gain nothing
    max_age=600,
)

for module in (auth, bookings):
    app.include_router(module.router)
app.include_router(experts.public)
app.include_router(experts.manage)


@app.get("/api/health")
def health():
    return {"status": "ok", "payments": config.payment_mode()}
