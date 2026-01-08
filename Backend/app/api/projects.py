from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from bson import ObjectId
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, Db
from app.core.config import settings
from app.db.gridfs import GridFsService
from app.domain.enums import UserRole
from app.domain.models import Project, User
from app.repositories.feedback import FeedbackRepository
from app.repositories.projects import ProjectRepository
from app.repositories.translator_languages import TranslatorLanguageRepository
from app.repositories.users import UserRepository
from app.services.emailer import EmailService
from app.services.project_review import ProjectReviewService
from app.services.project_service import ProjectService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectOut(BaseModel):
    """Short project representation used by create endpoint."""

    id: UUID
    customer_id: UUID
    translator_id: Optional[UUID] = None
    language_code: str
    state: str


class ProjectListItemOut(BaseModel):
    """Project list row returned to CUSTOMER/TRANSLATOR UI."""

    id: UUID
    language_code: str
    original_file_name: str | None = None
    state: str
    created_at: str | None = None

    customer_id: UUID
    customer_name: str | None = None

    translator_id: UUID | None = None
    translator_name: str | None = None


class AdminFeedbackProjectOut(BaseModel):
    """Project row used in the admin feedback view."""

    id: UUID
    language_code: str
    state: str
    customer_id: UUID
    customer_name: str | None = None
    customer_email: str | None = None
    translator_id: UUID | None = None
    translator_name: str | None = None
    translator_email: str | None = None
    feedback_text: str | None = None
    created_at: str | None = None


async def _map_gridfs_filenames(db, file_ids: list[str]) -> dict[str, str]:
    """Batch map GridFS file ids to filenames.

    Args:
        db: MongoDB database handle.
        file_ids: GridFS ObjectId values stored as strings.

    Returns:
        dict[str, str]: Mapping {file_id: filename}.
    """

    oids: list[ObjectId] = []
    for fid in file_ids:
        try:
            oids.append(ObjectId(fid))
        except Exception:
            continue

    if not oids:
        return {}

    cursor = db["files.files"].find({"_id": {"$in": oids}}, projection={"filename": 1})
    docs = await cursor.to_list(length=len(oids))
    return {str(d["_id"]): d.get("filename") for d in docs if d.get("filename")}


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    language_code: str = Form(..., min_length=2, max_length=2),
    original_file: UploadFile = File(...),
    db=Db,
    current_user: User = CurrentUser,
) -> ProjectOut:
    """Create a new translation project and assign a translator.

    Uploads the original file to GridFS and then delegates orchestration to
    `ProjectService`.

    Args:
        language_code: Target language (ISO 639-1).
        original_file: Uploaded file (any type).
        db: MongoDB database dependency.
        current_user: Authenticated user.

    Returns:
        ProjectOut: Created project representation.

    Raises:
        HTTPException: If user role is not CUSTOMER or upload is too large.
    """
    content = await original_file.read()

    project_repo = ProjectRepository(db)
    translator_lang_repo = TranslatorLanguageRepository(db)
    user_repo = UserRepository(db)
    fs = GridFsService(db)
    mailer = EmailService()

    svc = ProjectService(
        project_repo=project_repo,
        translator_lang_repo=translator_lang_repo,
        user_repo=user_repo,
        gridfs=fs,
        mailer=mailer,
    )

    result = await svc.create_project(
        customer=current_user,
        language_code=language_code,
        original_filename=original_file.filename or "upload.bin",
        content_type=original_file.content_type or "application/octet-stream",
        content=content,
    )

    p = result.project
    return ProjectOut(
        id=p.id,
        customer_id=p.customer_id,
        translator_id=p.translator_id,
        language_code=p.language_code,
        state=p.state.value if hasattr(p.state, "value") else str(p.state),
    )


@router.get("/{project_id}/original")
async def download_original_file(project_id: UUID, db=Db, current_user: User = CurrentUser):
    """Download the original file for a project.

    Access rules:
        - CUSTOMER: only own project
        - TRANSLATOR: only assigned project

    Args:
        project_id: Project UUID.
        db: MongoDB database dependency.
        current_user: Authenticated user.

    Returns:
        Response: File download response.

    Raises:
        HTTPException: If project/file is not found or access is denied.
    """
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if current_user.role == UserRole.CUSTOMER and project.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")
    if current_user.role == UserRole.TRANSLATOR and project.translator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    try:
        oid = ObjectId(project.original_file_id)
    except Exception:
        raise HTTPException(status_code=500, detail="Invalid file id")

    fs = GridFsService(db)
    data, info = await fs.download(oid)

    metadata = info.get("metadata") or {}
    content_type = metadata.get("content_type") or "application/octet-stream"
    filename = info.get("filename") or "download.bin"

    headers = {"Content-Disposition": f"attachment; filename=\"{filename}\""}
    return Response(content=data, media_type=content_type, headers=headers)


@router.get("/{project_id}", response_model=Project)
async def get_project(project_id: UUID, db=Db, current_user: User = CurrentUser) -> Project:
    """Get a project by id.

    Access rules:
        - CUSTOMER: only own project
        - TRANSLATOR: only assigned project

    Args:
        project_id: Project UUID.
        db: MongoDB database dependency.
        current_user: Authenticated user.

    Returns:
        Project: Full project model.
    """
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if current_user.role == UserRole.CUSTOMER and project.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")
    if current_user.role == UserRole.TRANSLATOR and project.translator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    return project


@router.get("", response_model=list[ProjectListItemOut])
async def list_projects(db=Db, current_user: User = CurrentUser) -> list[ProjectListItemOut]:
    """List projects for the current user.

    Behavior:
        - CUSTOMER: list projects created by the user
        - TRANSLATOR: list active projects assigned to the user

    Args:
        db: MongoDB database dependency.
        current_user: Authenticated user.

    Returns:
        list[ProjectListItemOut]: Project list rows.
    """
    project_repo = ProjectRepository(db)
    user_repo = UserRepository(db)

    if current_user.role == UserRole.CUSTOMER:
        projects = await project_repo.list_by_customer(current_user.id)
        translator_ids = sorted({p.translator_id for p in projects if p.translator_id is not None})
        translator_names = await user_repo.map_ids_to_names(translator_ids) if translator_ids else {}

        file_name_map = await _map_gridfs_filenames(db, [p.original_file_id for p in projects])

        return [
            ProjectListItemOut(
                id=p.id,
                language_code=p.language_code,
                original_file_name=file_name_map.get(p.original_file_id),
                state=p.state.value if hasattr(p.state, "value") else str(p.state),
                created_at=p.created_at.isoformat() if getattr(p, "created_at", None) else None,
                customer_id=p.customer_id,
                customer_name=None,
                translator_id=p.translator_id,
                translator_name=translator_names.get(str(p.translator_id)) if p.translator_id else None,
            )
            for p in projects
        ]

    if current_user.role == UserRole.TRANSLATOR:
        projects = await project_repo.list_by_translator(current_user.id)
        customer_ids = sorted({p.customer_id for p in projects})
        customer_names = await user_repo.map_ids_to_names(customer_ids) if customer_ids else {}

        file_name_map = await _map_gridfs_filenames(db, [p.original_file_id for p in projects])

        return [
            ProjectListItemOut(
                id=p.id,
                language_code=p.language_code,
                original_file_name=file_name_map.get(p.original_file_id),
                state=p.state.value if hasattr(p.state, "value") else str(p.state),
                created_at=p.created_at.isoformat() if getattr(p, "created_at", None) else None,
                customer_id=p.customer_id,
                customer_name=customer_names.get(str(p.customer_id)),
                translator_id=p.translator_id,
                translator_name=None,
            )
            for p in projects
        ]

    raise HTTPException(status_code=403, detail="Not implemented for this role")


@router.post("/{project_id}/translation", status_code=204)
async def submit_translation(
    project_id: UUID,
    translated_file: UploadFile = File(...),
    db=Db,
    current_user: User = CurrentUser,
) -> None:
    """Upload translated file for an assigned project.

    Uploads the translated file to GridFS, sets `translated_file_id` and moves the
    project state to COMPLETED. Notifies the customer by email.

    Args:
        project_id: Project UUID.
        translated_file: Uploaded translated file.
        db: MongoDB database dependency.
        current_user: Authenticated user.

    Raises:
        HTTPException: If project is not found, access is denied, state is invalid,
            or file exceeds max upload size.
    """
    if current_user.role != UserRole.TRANSLATOR:
        raise HTTPException(status_code=403, detail="Only translators can submit translations")

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.translator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    if project.state not in ("ASSIGNED", "COMPLETED") and getattr(project.state, "value", None) not in ("ASSIGNED", "COMPLETED"):
        raise HTTPException(status_code=409, detail="Project is not in a state that allows translation upload")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    content = await translated_file.read()
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Max upload size is {settings.max_upload_mb} MB")

    fs = GridFsService(db)
    file_id = await fs.upload(
        filename=translated_file.filename or "translation.bin",
        data=content,
        metadata={"content_type": translated_file.content_type or "application/octet-stream"},
    )

    ok = await repo.submit_translation(
        project_id=project_id,
        translator_id=current_user.id,
        translated_file_id=str(file_id),
    )
    if not ok:
        raise HTTPException(status_code=409, detail="Failed to update project")

    users = UserRepository(db)
    customer = await users.get_by_id(project.customer_id)
    if customer is not None:
        EmailService().send(
            to=str(customer.email_address),
            subject="Your translation is ready",
            text=(
                f"Hi {customer.name},\n\n"
                f"Your translation has been completed.\n"
                f"Project ID: {project_id}\n"
            ),
        )

    return None


@router.get("/{project_id}/translated")
async def download_translated_file(project_id: UUID, db=Db, current_user: User = CurrentUser):
    """Download the translated file for a project.

    Access rules:
        - CUSTOMER: only own project
        - TRANSLATOR: only assigned project

    Args:
        project_id: Project UUID.
        db: MongoDB database dependency.
        current_user: Authenticated user.

    Returns:
        Response: File download response.

    Raises:
        HTTPException: If file does not exist, project not found, or access is denied.
    """
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if current_user.role == UserRole.CUSTOMER and project.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")
    if current_user.role == UserRole.TRANSLATOR and project.translator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    if not project.translated_file_id:
        raise HTTPException(status_code=404, detail="Translated file not found")

    try:
        oid = ObjectId(project.translated_file_id)
    except Exception:
        raise HTTPException(status_code=500, detail="Invalid file id")

    fs = GridFsService(db)
    data, info = await fs.download(oid)

    metadata = info.get("metadata") or {}
    content_type = metadata.get("content_type") or "application/octet-stream"
    filename = info.get("filename") or "translated.bin"

    headers = {"Content-Disposition": f"attachment; filename=\"{filename}\""}
    return Response(content=data, media_type=content_type, headers=headers)


class ApproveIn(BaseModel):
    """Request body for approving a project (feedback is optional)."""

    text: str = Field(default="", max_length=2000)


class RejectIn(BaseModel):
    """Request body for rejecting a project (feedback is required)."""

    text: str = Field(min_length=1, max_length=2000)


@router.post("/{project_id}/approve", status_code=204)
async def approve_project(project_id: UUID, payload: ApproveIn, db=Db, current_user: User = CurrentUser) -> None:
    """Approve a completed translation and optionally submit feedback.

    Also notifies the translator by email.

    Args:
        project_id: Project UUID.
        payload: Approval payload.
        db: MongoDB database dependency.
        current_user: Authenticated user.

    Raises:
        HTTPException: If access denied or project state transition is not allowed.
    """
    if current_user.role != UserRole.CUSTOMER:
        raise HTTPException(status_code=403, detail="Only customers can approve")

    repo = ProjectRepository(db)
    feedback_repo = FeedbackRepository(db)
    svc = ProjectReviewService(repo, feedback_repo)

    res = await svc.approve(project_id=project_id, customer_id=current_user.id, text=payload.text)
    if res is None:
        raise HTTPException(status_code=409, detail="Project is not in COMPLETED state")

    project = await repo.get_by_id(project_id)
    if project and project.translator_id:
        users = UserRepository(db)
        translator = await users.get_by_id(project.translator_id)
        if translator is not None:
            EmailService().send(
                to=str(translator.email_address),
                subject="Translation approved",
                text=(
                    f"Hi {translator.name},\n\n"
                    f"Customer approved the translation.\n"
                    f"Project ID: {project_id}\n"
                ),
            )

    return None


@router.post("/{project_id}/reject", status_code=204)
async def reject_project(project_id: UUID, payload: RejectIn, db=Db, current_user: User = CurrentUser) -> None:
    """Reject a completed translation and submit feedback.

    Also notifies the translator by email.

    Args:
        project_id: Project UUID.
        payload: Rejection payload.
        db: MongoDB database dependency.
        current_user: Authenticated user.

    Raises:
        HTTPException: If access denied or project state transition is not allowed.
    """
    if current_user.role != UserRole.CUSTOMER:
        raise HTTPException(status_code=403, detail="Only customers can reject")

    repo = ProjectRepository(db)
    feedback_repo = FeedbackRepository(db)
    svc = ProjectReviewService(repo, feedback_repo)

    res = await svc.reject(project_id=project_id, customer_id=current_user.id, text=payload.text)
    if res is None:
        raise HTTPException(status_code=409, detail="Project is not in COMPLETED state")

    project = await repo.get_by_id(project_id)
    if project and project.translator_id:
        users = UserRepository(db)
        translator = await users.get_by_id(project.translator_id)
        if translator is not None:
            EmailService().send(
                to=str(translator.email_address),
                subject="Translation rejected",
                text=(
                    f"Hi {translator.name},\n\n"
                    f"Customer rejected the translation and left feedback.\n"
                    f"Project ID: {project_id}\n"
                ),
            )

    return None


@router.get("/admin/feedback", response_model=list[AdminFeedbackProjectOut])
async def admin_list_projects_with_feedback(
    state: str | None = None,
    db=Db,
    current_user: User = CurrentUser,
) -> list[AdminFeedbackProjectOut]:
    """List projects with feedback for administrator view.

    Args:
        state: Optional state filter.
        db: MongoDB database dependency.
        current_user: Authenticated user.

    Returns:
        list[AdminFeedbackProjectOut]: Projects with feedback and user details.

    Raises:
        HTTPException: If current user is not ADMINISTRATOR.
    """
    if current_user.role != UserRole.ADMINISTRATOR:
        raise HTTPException(status_code=403, detail="Only administrators")

    user_repo = UserRepository(db)
    fb_repo = FeedbackRepository(db)

    query: dict = {"$or": [{"feedback_id": {"$exists": True, "$ne": None}}, {"feedback": {"$ne": None}}]}
    if state:
        query["state"] = state

    cursor = db["projects"].find(query).sort("created_at", -1)
    docs = await cursor.to_list(length=200)
    projects = [Project.model_validate(d) for d in docs]

    customer_ids = sorted({p.customer_id for p in projects})
    translator_ids = sorted({p.translator_id for p in projects if p.translator_id is not None})

    customers = {str(u.id): u for u in await user_repo.list_by_ids(customer_ids)} if customer_ids else {}
    translators = {str(u.id): u for u in await user_repo.list_by_ids(translator_ids)} if translator_ids else {}

    out: list[AdminFeedbackProjectOut] = []
    for p in projects:
        fb_text = None
        if getattr(p, "feedback", None) is not None:
            fb_text = p.feedback.text
        else:
            fb = await fb_repo.get_by_project_id(p.id)
            fb_text = fb.text if fb else None

        cu = customers.get(str(p.customer_id))
        tu = translators.get(str(p.translator_id)) if p.translator_id else None

        out.append(
            AdminFeedbackProjectOut(
                id=p.id,
                language_code=p.language_code,
                state=p.state.value if hasattr(p.state, "value") else str(p.state),
                customer_id=p.customer_id,
                customer_name=cu.name if cu else None,
                customer_email=str(cu.email_address) if cu else None,
                translator_id=p.translator_id,
                translator_name=tu.name if tu else None,
                translator_email=str(tu.email_address) if tu else None,
                feedback_text=fb_text,
                created_at=p.created_at.isoformat() if getattr(p, "created_at", None) else None,
            )
        )

    return out


class AdminMessageIn(BaseModel):
    """Request body for admin message endpoint."""

    to: str = Field(description="customer|translator")
    subject: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=4000)


@router.post("/admin/projects/{project_id}/message", status_code=204)
async def admin_send_message(
    project_id: UUID,
    payload: AdminMessageIn,
    db=Db,
    current_user: User = CurrentUser,
) -> None:
    """Send an admin message to customer or translator.

    Args:
        project_id: Project UUID.
        payload: Message payload.
        db: MongoDB database dependency.
        current_user: Authenticated user.

    Raises:
        HTTPException: If not admin, project not found, target not found or invalid.
    """
    if current_user.role != UserRole.ADMINISTRATOR:
        raise HTTPException(status_code=403, detail="Only administrators")

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    users = UserRepository(db)
    customer = await users.get_by_id(project.customer_id)
    translator = await users.get_by_id(project.translator_id) if project.translator_id else None

    target = (payload.to or "").lower()
    if target == "customer":
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found")
        EmailService().send(
            to=str(customer.email_address),
            subject=payload.subject,
            text=f"[Project {project_id}]\n\n{payload.text}",
        )
        return None

    if target == "translator":
        if translator is None:
            raise HTTPException(status_code=404, detail="Translator not found")
        EmailService().send(
            to=str(translator.email_address),
            subject=payload.subject,
            text=f"[Project {project_id}]\n\n{payload.text}",
        )
        return None

    raise HTTPException(status_code=422, detail="Invalid 'to' (use 'customer' or 'translator')")


@router.post("/admin/projects/{project_id}/close", status_code=204)
async def admin_close_project(project_id: UUID, db=Db, current_user: User = CurrentUser) -> None:
    """Close a project as an administrator.

    Notifies both customer and translator by email (if present).

    Args:
        project_id: Project UUID.
        db: MongoDB database dependency.
        current_user: Authenticated user.

    Raises:
        HTTPException: If not admin or project not found.
    """
    if current_user.role != UserRole.ADMINISTRATOR:
        raise HTTPException(status_code=403, detail="Only administrators")

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    await repo.close_project(project_id)

    users = UserRepository(db)
    customer = await users.get_by_id(project.customer_id)
    translator = await users.get_by_id(project.translator_id) if project.translator_id else None

    mailer = EmailService()
    if customer is not None:
        mailer.send(
            to=str(customer.email_address),
            subject="Project closed",
            text=f"Hi {customer.name},\n\nProject {project_id} has been closed by administrator.\n",
        )
    if translator is not None:
        mailer.send(
            to=str(translator.email_address),
            subject="Project closed",
            text=f"Hi {translator.name},\n\nProject {project_id} has been closed by administrator.\n",
        )

    return None
