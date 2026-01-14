import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, messages, sandbox, sessions
from app.config import get_settings
from app.database import init_db

# 导入所有模型以确保 SQLAlchemy 创建表

settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="AI Agent Sandbox",
    description="An AI-powered web development sandbox",
    version="1.0.0"
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


@app.get("/")
async def root():
    """Landing page - public access."""
    landing_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(landing_path):
        return FileResponse(landing_path)
    return {"error": "Landing page not found"}


@app.get("/chat/{session_id}")
async def chat_workspace(session_id: str):
    """Chat workspace for a specific session."""
    workspace_path = os.path.join(os.path.dirname(__file__), "static", "app.html")
    if os.path.exists(workspace_path):
        return FileResponse(workspace_path)
    return {"error": "Workspace page not found"}


@app.get("/sign-in")
async def sign_in():
    """Sign in page."""
    login_path = os.path.join(os.path.dirname(__file__), "static", "login.html")
    if os.path.exists(login_path):
        return FileResponse(login_path)
    return {"error": "Login page not found"}


@app.get("/register")
async def register_page():
    """Register page."""
    register_path = os.path.join(os.path.dirname(__file__), "static", "register.html")
    if os.path.exists(register_path):
        return FileResponse(register_path)
    return {"error": "Register page not found"}


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
