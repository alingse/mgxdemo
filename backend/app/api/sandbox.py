import aiofiles
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_current_user_optional
from app.database import get_db
from app.models.session import Session as SessionModel
from app.models.user import User
from app.services.sandbox_service import get_sandbox_service

router = APIRouter(prefix="/api/sessions/{session_id}/sandbox", tags=["sandbox"])


def _verify_session_access(session_id: str, user_id: int, db: Session) -> SessionModel:
    """Verify user has access to the session."""
    session = (
        db.query(SessionModel)
        .filter(SessionModel.id == session_id, SessionModel.user_id == user_id)
        .first()
    )

    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    return session


class FileUpdate(BaseModel):
    """File update model."""

    content: str


@router.get("/files", response_model=list[str])
async def list_files(
    session_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """List all files in the sandbox."""
    _verify_session_access(session_id, current_user.id, db)
    sandbox_service = get_sandbox_service()
    files = await sandbox_service.list_files(current_user.id, session_id)
    return files


@router.get("/files/{filename}")
async def get_file(
    session_id: str,
    filename: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a file's content from the sandbox."""
    _verify_session_access(session_id, current_user.id, db)
    sandbox_service = get_sandbox_service()

    try:
        content = await sandbox_service.read_file(current_user.id, session_id, filename)
        return {"filename": filename, "content": content}
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {filename}",
        ) from None


@router.post("/files/{filename}", status_code=status.HTTP_201_CREATED)
async def create_or_update_file(
    session_id: str,
    filename: str,
    file_update: FileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update a file in the sandbox."""
    _verify_session_access(session_id, current_user.id, db)
    sandbox_service = get_sandbox_service()

    try:
        await sandbox_service.write_file(current_user.id, session_id, filename, file_update.content)
        return {"filename": filename, "status": "saved"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.delete("/files/{filename}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    session_id: str,
    filename: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a file from the sandbox."""
    _verify_session_access(session_id, current_user.id, db)
    sandbox_service = get_sandbox_service()
    await sandbox_service.delete_file(current_user.id, session_id, filename)


@router.get("/preview")
async def preview_sandbox(
    session_id: str,
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Preview the sandbox as HTML."""
    # Get session to check if it's public
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Check access: either owner or public session
    if not session.is_public:
        if not current_user or current_user.id != session.user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="This session is private"
            )

    sandbox_service = get_sandbox_service()
    sandbox_path = sandbox_service._get_sandbox_path(session.user_id, session_id)
    index_path = sandbox_path / "index.html"

    if not index_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="index.html not found in sandbox"
        )

    # Read the HTML content
    async with aiofiles.open(index_path) as f:
        html_content = await f.read()

    # Inject base tag to fix resource paths
    # Resources should be loaded from /api/sessions/{session_id}/sandbox/static/
    base_tag = f'<base href="/api/sessions/{session_id}/sandbox/static/">'

    # Insert base tag after <head> or at the beginning if no <head>
    if "<head>" in html_content:
        html_content = html_content.replace("<head>", f"<head>\n    {base_tag}", 1)
    else:
        html_content = base_tag + html_content

    return HTMLResponse(content=html_content, headers={"Cache-Control": "no-cache"})


@router.get("/static/{filename}")
async def get_static_file(
    session_id: str,
    filename: str,
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Get a static file (CSS, JS) from the sandbox."""
    # Get session to check if it's public
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Check access: either owner or public session
    if not session.is_public:
        if not current_user or current_user.id != session.user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="This session is private"
            )

    sandbox_service = get_sandbox_service()
    sandbox_path = sandbox_service._get_sandbox_path(session.user_id, session_id)
    file_path = sandbox_path / filename

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found: {filename}"
        )

    # Determine media type
    media_type = "text/plain"
    if filename.endswith(".css"):
        media_type = "text/css"
    elif filename.endswith(".js"):
        media_type = "application/javascript"
    elif filename.endswith(".html"):
        media_type = "text/html"

    return FileResponse(
        path=str(file_path), media_type=media_type, headers={"Cache-Control": "no-cache"}
    )
