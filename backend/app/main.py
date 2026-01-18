import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, messages, sandbox, sessions
from app.config import get_settings
from app.database import init_db

settings = get_settings()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
# Set specific loggers to INFO level
logging.getLogger("app").setLevel(logging.INFO)
logging.getLogger("app.api").setLevel(logging.INFO)
logging.getLogger("app.services").setLevel(logging.INFO)

# Create FastAPI app
app = FastAPI(
    title="AI Agent Sandbox", description="An AI-powered web development sandbox", version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(sessions.router)
app.include_router(messages.router)
app.include_router(sandbox.router)

# Mount static files
frontend_static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(frontend_static_path):
    app.mount("/static", StaticFiles(directory=frontend_static_path), name="static")


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()
    # Ensure sandbox directory exists
    os.makedirs(settings.sandbox_base_dir, exist_ok=True)


# Static page routes configuration
STATIC_PAGE_ROUTES = {
    "/": ("index.html", "Landing page"),
    "/sign-in": ("login.html", "Login page"),
    "/register": ("register.html", "Register page"),
    "/about": ("about.html", "About page"),
    "/contact": ("contact.html", "Contact page"),
    "/terms": ("terms.html", "Terms page"),
    "/privacy": ("privacy.html", "Privacy page"),
    "/docs/getting-started": ("getting-started.html", "Getting started page"),
    "/docs/user-guide": ("user-guide.html", "User guide page"),
    "/docs/api": ("api.html", "API documentation page"),
    "/docs/faq": ("faq.html", "FAQ page"),
}


def _serve_static_html(filename: str, page_name: str):
    """Serve a static HTML file from the static directory."""
    file_path = os.path.join(os.path.dirname(__file__), "static", filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return {"error": f"{page_name} not found"}


def _create_page_handler(filename: str, page_name: str):
    """Factory function to create a page handler with captured values."""
    async def page_handler():
        return _serve_static_html(filename, page_name)
    return page_handler


# Register static page routes dynamically
for route, (filename, page_name) in STATIC_PAGE_ROUTES.items():
    handler = _create_page_handler(filename, page_name)
    app.get(route)(handler)


@app.get("/chat/{session_id}")
async def chat_workspace(session_id: str):
    """Chat workspace for a specific session."""
    workspace_path = os.path.join(os.path.dirname(__file__), "static", "app.html")
    if os.path.exists(workspace_path):
        return FileResponse(workspace_path)
    return {"error": "Workspace page not found"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/app/{session_id}")
async def app_preview(session_id: str):
    """Standalone preview page for a session."""
    preview_html_path = os.path.join(os.path.dirname(__file__), "static", "preview.html")
    if os.path.exists(preview_html_path):
        return FileResponse(preview_html_path)
    return {"error": "Preview page not found"}
