
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.session import Session as SessionModel
from app.models.user import User
from app.schemas.session import SessionCreate, SessionDetail, SessionResponse, SessionUpdate
from app.services.sandbox_service import get_sandbox_service

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all sessions for the current user."""
    sessions = db.query(SessionModel).filter(
        SessionModel.user_id == current_user.id
    ).order_by(SessionModel.updated_at.desc()).all()
    return sessions


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    session_create: SessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new session."""
    db_session = SessionModel(
        user_id=current_user.id,
        title=session_create.title
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)

    # Initialize sandbox for the session
    sandbox_service = get_sandbox_service()
    await sandbox_service.initialize_sandbox(current_user.id, db_session.id)

    return db_session


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a session by ID."""
    session = db.query(SessionModel).filter(
        SessionModel.id == session_id,
        SessionModel.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    return session


@router.put("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    session_update: SessionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a session (title, is_public, etc.)."""
    session = db.query(SessionModel).filter(
        SessionModel.id == session_id,
        SessionModel.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    # Update fields if provided
    if session_update.title is not None:
        session.title = session_update.title
    if session_update.is_public is not None:
        session.is_public = session_update.is_public

    db.commit()
    db.refresh(session)

    return session


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a session."""
    session = db.query(SessionModel).filter(
        SessionModel.id == session_id,
        SessionModel.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    # Delete sandbox
    sandbox_service = get_sandbox_service()
    await sandbox_service.delete_sandbox(current_user.id, session_id)

    db.delete(session)
    db.commit()


@router.websocket("/ws/{session_id}")
async def websocket_session(
    session_id: str,
    websocket: WebSocket,
    db: Session = Depends(get_db)
):
    """WebSocket endpoint for real-time session updates."""
    await websocket.accept()

    # Verify session exists
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_json()
            # Process and send back responses
            await websocket.send_json({"type": "echo", "data": data})
    except WebSocketDisconnect:
        pass
