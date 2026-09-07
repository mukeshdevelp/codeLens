"""CodeLens FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.db import init_db
from app.routers import api, auth, github_integration, webhooks

app = FastAPI(title="CodeLens API", version="1.0.0")

_origins = [
    settings.frontend_url,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
if settings.embed_allowed_frame_ancestors:
    _origins.append("https://github.com")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"https://.*\.trycloudflare\.com|https://.*\.loca\.lt",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class EmbedFrameMiddleware(BaseHTTPMiddleware):
    """Allow github.com to iframe embed routes when ``EMBED_ALLOWED_FRAME_ANCESTORS`` is set."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/api/github/embed/") and settings.embed_allowed_frame_ancestors:
            ancestors = settings.embed_allowed_frame_ancestors.strip()
            response.headers["Content-Security-Policy"] = f"frame-ancestors {ancestors} 'self'"
        return response


app.add_middleware(EmbedFrameMiddleware)

app.include_router(auth.router)
app.include_router(api.router)
app.include_router(webhooks.router)
app.include_router(github_integration.router)


@app.on_event("startup")
async def startup() -> None:
    await init_db()
    if settings.github_client_id:
        print(
            "GitHub OAuth: set Authorization callback URL to",
            settings.github_redirect_uri,
            "→ https://github.com/settings/developers",
        )


@app.get("/health")
async def health():
    """Liveness probe for Docker, Kubernetes, and load balancers."""
    return {"status": "ok", "service": "codelens-api"}
