from __future__ import annotations

import hashlib
from io import BytesIO
from typing import TypedDict, cast

from django.conf import settings
from django.contrib import messages
from django.contrib.sessions.backends.base import SessionBase
from django.http import FileResponse, HttpRequest, HttpResponse
from django.http.response import HttpResponseBase
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from web.backend_client import (
    add_translator_language,
    admin_close_project,
    admin_list_feedback_projects,
    admin_send_project_message,
    approve_project as backend_approve_project,
    create_project as backend_create_project,
    delete_translator_language,
    download_project_original,
    download_project_translated,
    get_feedback_by_project,
    get_project,
    list_projects as backend_list_projects,
    list_translator_languages,
    otp_enable as backend_otp_enable,
    reject_project as backend_reject_project,
    submit_translation as backend_submit_translation, BackendResponse,
    ProjectListItemOut,
    AdminFeedbackProjectOut,
)

from web.backend_client import login as backend_login
from web.backend_client import otp_login as backend_otp_login
from web.backend_client import register_user
from web.forms import LoginForm, RegisterForm
from web.language_forms import LanguageAddForm, LanguageRemoveForm
from web.project_forms import ProjectCreateForm
from web.translator_forms import TranslationUploadForm
from web.customer_forms import FeedbackForm
from web.admin_forms import AdminMessageForm


class SessionUser(TypedDict, total=False):
    user_id: str
    role: str
    username: str

def _sha256_hex(value: str) -> str:
    """Return SHA-256 hex digest of a string.

    Note:
        This helper is kept for compatibility; passwords are sent as plaintext to
        the backend and hashed server-side.

    Args:
        value: Input string.

    Returns:
        str: Hex digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def home(request: HttpRequest) -> HttpResponse:
    """Render the home page."""
    return render(request, "web/home.html")


def _session(request: HttpRequest) -> SessionBase:
    """Return request.session as a SessionBase for typing purposes."""
    return cast(SessionBase, getattr(request, "session"))


def _require_roles(request: HttpRequest, allowed: set[str]) -> SessionUser:
    """Ensure the user is authenticated and has one of the allowed roles.

    Args:
        request: Django request.
        allowed: Allowed role names.

    Returns:
        SessionUser: Session user dict.

    Raises:
        PermissionError: If missing session user or role is not allowed.
    """
    user_obj = _session(request).get(settings.SESSION_USER_KEY)
    if not user_obj:
        raise PermissionError("Not authenticated")

    user = cast(SessionUser, user_obj)
    role = (user.get("role") or "").upper()
    if role not in allowed:
        raise PermissionError("Forbidden")
    return user


def languages_view(request: HttpRequest) -> HttpResponse:
    """Manage translator languages.

    Visible for TRANSLATOR and ADMINISTRATOR.

    The view reads current languages from backend and allows adding/removing
    languages via backend endpoints.
    """

    try:
        user: SessionUser = _require_roles(request, {"TRANSLATOR", "ADMINISTRATOR"})
    except PermissionError:
        messages.error(request, _("Not allowed"))
        return redirect("home")

    token = _session(request).get(settings.SESSION_JWT_KEY)
    if not token:
        messages.error(request, _("Not authenticated"))
        return redirect("login")

    translator_id = user.get("user_id")
    if not translator_id:
        messages.error(request, _("Missing user id"))
        return redirect("home")

    languages: list[str] = []

    add_form: LanguageAddForm = LanguageAddForm()

    if request.method == "POST":
        action: str | None = request.POST.get("action")

        if action == "remove":
            remove_form: LanguageRemoveForm = LanguageRemoveForm(request.POST)
            if remove_form.is_valid():
                code = remove_form.cleaned_data["language_code"]
                resp: BackendResponse = delete_translator_language(
                    translator_id=str(translator_id),
                    language_code=code,
                    token=str(token),
                )
                if resp.status in (200, 204):
                    messages.success(request, _("Language removed"))
                    return redirect("languages")

                detail: str | None = (resp.data or {}).get("detail") or _("Failed to remove language")
                messages.error(request, str(detail))
            else:
                messages.error(request, _("Invalid remove request"))

        else:
            add_form = LanguageAddForm(request.POST)
            if add_form.is_valid():
                resp = add_translator_language(
                    translator_id=str(translator_id),
                    language_code=add_form.cleaned_data["language_code"],
                    token=str(token),
                )
                if resp.status in (200, 201):
                    messages.success(request, _("Language added"))
                    return redirect("languages")

                detail = (resp.data or {}).get("detail") or _("Failed to add language")
                messages.error(request, str(detail))
            else:
                messages.error(request, _("Please fix the form errors."))

    resp = list_translator_languages(translator_id=str(translator_id), token=str(token))
    if resp.status == 200 and resp.data:
        languages = resp.data.get("languages") or []
    else:
        detail = (resp.data or {}).get("detail") or _("Failed to load languages")
        messages.error(request, str(detail))

    return render(
        request,
        "web/languages.html",
        {
            "form": add_form,
            "languages": languages,
        },
    )


def login_view(request: HttpRequest) -> HttpResponse:
    """Login UX.

    Supports two methods:
    - password-based login
    - OTP (TOTP) login (requires prior activation)
    """
    if request.method == "POST":
        form: LoginForm = LoginForm(request.POST)
        if form.is_valid():
            username: str = form.cleaned_data["username"]
            method: str | None = form.cleaned_data.get("method") or "password"

            if method == "otp":
                resp = backend_otp_login(username=username, otp=(form.cleaned_data.get("otp") or "").strip())
            else:
                resp = backend_login(username=username, password=form.cleaned_data["password"])

            if resp.status == 200 and resp.data:
                _session(request)[settings.SESSION_JWT_KEY] = resp.data.get("access_token")
                _session(request)[settings.SESSION_USER_KEY] = {
                    "user_id": resp.data.get("user_id"),
                    "role": resp.data.get("role"),
                    "username": username,
                }
                messages.success(request, _("Logged in"))
                return redirect("home")

            detail: str | None = (resp.data or {}).get("detail") or _("Login failed")
            messages.error(request, str(detail))
        else:
            messages.error(request, _("Please fix the form errors."))
    else:
        form = LoginForm()

    return render(request, "web/login.html", {"form": form})


def register_view(request: HttpRequest) -> HttpResponse:
    """Register UX.

    Creates a CUSTOMER or TRANSLATOR account using the backend API.
    """
    if request.method == "POST":
        form: RegisterForm = RegisterForm(request.POST)
        if form.is_valid():
            resp: BackendResponse = register_user(
                name=form.cleaned_data["name"],
                email_address=form.cleaned_data["email_address"],
                password=form.cleaned_data["password"],
                role=form.cleaned_data["role"],
            )

            if resp.status in (200, 201):
                messages.success(request, _("Account created. You can log in now."))
                return redirect("login")

            detail: str | None = (resp.data or {}).get("detail") or _("Registration failed")
            messages.error(request, str(detail))
        else:
            messages.error(request, _("Please fix the form errors."))
    else:
        form = RegisterForm()

    return render(request, "web/register.html", {"form": form})


def logout_view(request: HttpRequest) -> HttpResponse:
    """Log out by clearing session keys."""
    _session(request).pop(settings.SESSION_JWT_KEY, None)
    _session(request).pop(settings.SESSION_USER_KEY, None)
    messages.info(request, _("Logged out"))
    return redirect("home")


def create_project_view(request: HttpRequest) -> HttpResponse:
    """Customer UI for creating a project and uploading the original file."""
    try:
        user: SessionUser = _require_roles(request, {"CUSTOMER"})
    except PermissionError:
        messages.error(request, _("Only customers can create projects"))
        return redirect("home")

    token = _session(request).get(settings.SESSION_JWT_KEY)
    if not token:
        messages.error(request, _("Not authenticated"))
        return redirect("login")

    if request.method == "POST":
        form: ProjectCreateForm = ProjectCreateForm(request.POST, request.FILES)
        if form.is_valid():
            f = form.cleaned_data["original_file"]
            content_type = getattr(f, "content_type", None) or "application/octet-stream"

            resp: BackendResponse = backend_create_project(
                language_code=form.cleaned_data["language_code"],
                file_name=getattr(f, "name", "upload.bin"),
                file_bytes=f.read(),
                content_type=content_type,
                token=str(token),
            )

            if resp.status in (200, 201) and resp.data:
                messages.success(request, _("Project created"))
                return redirect("home")

            detail: str | None = (resp.data or {}).get("detail") or _("Failed to create project")
            messages.error(request, str(detail))
        else:
            messages.error(request, _("Please fix the form errors."))
    else:
        form = ProjectCreateForm()

    return render(request, "web/create_project.html", {"form": form})


def projects_view(request: HttpRequest) -> HttpResponse:
    """List projects view.

    Behavior depends on role:
    - CUSTOMER / TRANSLATOR: list own projects
    - ADMINISTRATOR: shows projects with feedback using admin endpoint
    """
    try:
        user: SessionUser = _require_roles(request, {"CUSTOMER", "TRANSLATOR", "ADMINISTRATOR"})
    except PermissionError:
        messages.error(request, _("Not authenticated"))
        return redirect("login")

    token = _session(request).get(settings.SESSION_JWT_KEY)
    if not token:
        messages.error(request, _("Not authenticated"))
        return redirect("login")

    role: str = (user.get("role") or "").upper()

    if role == "ADMINISTRATOR":
        resp: BackendResponse[list[AdminFeedbackProjectOut]] = admin_list_feedback_projects(token=str(token))
        if resp.status != 200 or resp.data is None:
            detail = (resp.data or {}).get("detail") or _("Failed to load projects")
            messages.error(request, str(detail))
            projects_admin: list[AdminFeedbackProjectOut] = []
        else:
            projects_admin = resp.data

        return render(request, "web/projects_admin.html", {"projects": projects_admin, "role": role})

    resp: BackendResponse[list[ProjectListItemOut]] = backend_list_projects(token=str(token))
    if resp.status != 200 or resp.data is None:
        detail = (resp.data or {}).get("detail") or _("Failed to load projects")
        messages.error(request, str(detail))
        projects: list[ProjectListItemOut] = []
    else:
        projects = resp.data

    return render(request, "web/projects.html", {"projects": projects, "role": role})


def project_detail_translator_view(request: HttpRequest, project_id: str) -> HttpResponse:
    """Translator detail view.

    Allows downloading the original file and uploading translated file.
    Also displays last feedback (if any).
    """
    try:
        user: SessionUser = _require_roles(request, {"TRANSLATOR"})
    except PermissionError:
        messages.error(request, _("Not allowed"))
        return redirect("login")

    token = _session(request).get(settings.SESSION_JWT_KEY)
    if not token:
        messages.error(request, _("Not authenticated"))
        return redirect("login")

    resp: BackendResponse[list[ProjectListItemOut]] = backend_list_projects(token=str(token))
    if resp.status != 200 or resp.data is None:
        detail: str | None = (resp.data or {}).get("detail") or _("Failed to load project")
        messages.error(request, str(detail))
        return redirect("projects")

    project: ProjectListItemOut | None = next((p for p in resp.data if str(p.get("id")) == str(project_id)), None)
    if project is None:
        messages.error(request, _("Project not found"))
        return redirect("projects")

    has_translated_file: bool = False
    detail_resp: BackendResponse = get_project(project_id=str(project_id), token=str(token))
    if detail_resp.status == 200 and detail_resp.data:
        has_translated_file = bool(detail_resp.data.get("translated_file_id"))

    feedback_text: str | None = None
    fb_resp = get_feedback_by_project(project_id=str(project_id), token=str(token))
    if fb_resp.status == 200 and fb_resp.data:
        feedback_text = fb_resp.data.get("text")

    form: TranslationUploadForm = TranslationUploadForm()
    if request.method == "POST":
        form = TranslationUploadForm(request.POST, request.FILES)
        if form.is_valid():
            f = form.cleaned_data["translated_file"]
            content_type: str | None = getattr(f, "content_type", None) or "application/octet-stream"
            res: BackendResponse = backend_submit_translation(
                project_id=str(project_id),
                file_name=getattr(f, "name", "translation.bin"),
                file_bytes=f.read(),
                content_type=content_type,
                token=str(token),
            )

            if res.status in (200, 201, 204):
                messages.success(request, _("Translation uploaded. Customer will be notified by email."))
                return redirect("projects")

            detail = (res.data or {}).get("detail") or _("Failed to upload translation")
            messages.error(request, str(detail))
        else:
            messages.error(request, _("Please fix the form errors."))

    return render(
        request,
        "web/project_detail_translator.html",
        {
            "project": project,
            "form": form,
            "feedback_text": feedback_text,
            "has_translated_file": has_translated_file,
        },
    )


def project_original_proxy_view(request: HttpRequest, project_id: str) -> HttpResponseBase:
    """Proxy original file download through Django.

    Django downloads bytes from the backend and returns them as an attachment.
    This avoids exposing backend directly to the browser.
    """
    try:
        _require_roles(request, {"TRANSLATOR", "CUSTOMER"})
    except PermissionError:
        messages.error(request, _("Not allowed"))
        return redirect("login")

    token = _session(request).get(settings.SESSION_JWT_KEY)
    if not token:
        messages.error(request, _("Not authenticated"))
        return redirect("login")

    status, data, headers = download_project_original(project_id=str(project_id), token=str(token))
    if status != 200:
        messages.error(request, _("Failed to download file"))
        return redirect("projects")

    filename: str = "download.bin"
    cd: str | None = headers.get("Content-Disposition") or headers.get("content-disposition")
    if cd and "filename=" in cd:
        filename = cd.split("filename=")[-1].strip().strip('"')

    return FileResponse(BytesIO(data), as_attachment=True, filename=filename)


def project_detail_customer_view(request: HttpRequest, project_id: str) -> HttpResponse:
    """Customer detail view.

    Shows project info, allows downloading translated file (if present) and
    approving/rejecting with feedback.
    """
    try:
        _require_roles(request, {"CUSTOMER"})
    except PermissionError:
        messages.error(request, _("Not allowed"))
        return redirect("login")

    token = _session(request).get(settings.SESSION_JWT_KEY)
    if not token:
        messages.error(request, _("Not authenticated"))
        return redirect("login")

    resp: BackendResponse[list[ProjectListItemOut]] = backend_list_projects(token=str(token))
    if resp.status != 200 or resp.data is None:
        detail = (resp.data or {}).get("detail") or _("Failed to load project")
        messages.error(request, str(detail))
        return redirect("projects")

    project: ProjectListItemOut | None = next((p for p in resp.data if str(p.get("id")) == str(project_id)), None)
    if project is None:
        messages.error(request, _("Project not found"))
        return redirect("projects")

    has_translated_file: bool = False
    detail_resp: BackendResponse = get_project(project_id=str(project_id), token=str(token))
    if detail_resp.status == 200 and detail_resp.data:
        has_translated_file = bool(detail_resp.data.get("translated_file_id"))

    feedback_text: str | None = None
    fb_resp: BackendResponse = get_feedback_by_project(project_id=str(project_id), token=str(token))
    if fb_resp.status == 200 and fb_resp.data:
        feedback_text = fb_resp.data.get("text")

    form: FeedbackForm = FeedbackForm()

    return render(
        request,
        "web/project_detail_customer.html",
        {"project": project, "form": form, "feedback_text": feedback_text, "has_translated_file": has_translated_file},
    )


def project_translated_proxy_view(request: HttpRequest, project_id: str) -> HttpResponseBase:
    """Proxy translated file download through Django."""
    try:
        _require_roles(request, {"CUSTOMER", "TRANSLATOR"})
    except PermissionError:
        messages.error(request, _("Not allowed"))
        return redirect("login")

    token = _session(request).get(settings.SESSION_JWT_KEY)
    if not token:
        messages.error(request, _("Not authenticated"))
        return redirect("login")

    status, data, headers = download_project_translated(project_id=str(project_id), token=str(token))
    if status != 200:
        messages.error(request, _("Failed to download translated file"))
        return redirect("projects")

    filename: str = "translated.bin"
    cd: str | None = headers.get("Content-Disposition") or headers.get("content-disposition")
    if cd and "filename=" in cd:
        filename = cd.split("filename=")[-1].strip().strip('"')

    return FileResponse(BytesIO(data), as_attachment=True, filename=filename)


def project_approve_view(request: HttpRequest, project_id: str) -> HttpResponse:
    """Handle project approval action from customer UI."""
    try:
        _require_roles(request, {"CUSTOMER"})
    except PermissionError:
        messages.error(request, _("Not allowed"))
        return redirect("login")

    if request.method != "POST":
        return redirect("projects")

    token = _session(request).get(settings.SESSION_JWT_KEY)
    if not token:
        messages.error(request, _("Not authenticated"))
        return redirect("login")

    form: FeedbackForm = FeedbackForm(request.POST)
    if not form.is_valid():
        messages.error(request, _("Please fix the form errors."))
        return redirect("project_detail_customer", project_id=project_id)

    text: str | None = (form.cleaned_data.get("text") or "")

    res: BackendResponse = backend_approve_project(project_id=str(project_id), token=str(token), text=text)
    if res.status in (200, 204):
        messages.success(request, _("Approved"))
    else:
        detail: str | None = (res.data or {}).get("detail") or _("Failed to approve")
        messages.error(request, str(detail))

    return redirect("projects")


def project_reject_view(request: HttpRequest, project_id: str) -> HttpResponse:
    """Handle project rejection action from customer UI."""
    try:
        _require_roles(request, {"CUSTOMER"})
    except PermissionError:
        messages.error(request, _("Not allowed"))
        return redirect("login")

    if request.method != "POST":
        return redirect("projects")

    token = _session(request).get(settings.SESSION_JWT_KEY)
    if not token:
        messages.error(request, _("Not authenticated"))
        return redirect("login")

    form: FeedbackForm = FeedbackForm(request.POST)
    text: str = (request.POST.get("text") or "").strip()

    if not text:
        form.add_error("text", _("Feedback is required when rejecting."))

    if not form.is_valid() or not text:
        resp: BackendResponse = backend_list_projects(token=str(token))
        project: ProjectListItemOut | None = None
        if resp.status == 200 and resp.data:
            project = next((p for p in resp.data if str(p.get("id")) == str(project_id)), None)
        if project is None:
            messages.error(request, _("Project not found"))
            return redirect("projects")

        has_translated_file: bool = False
        detail_resp: BackendResponse = get_project(project_id=str(project_id), token=str(token))
        if detail_resp.status == 200 and detail_resp.data:
            has_translated_file = bool(detail_resp.data.get("translated_file_id"))

        feedback_text: str | None = None
        fb_resp: BackendResponse = get_feedback_by_project(project_id=str(project_id), token=str(token))
        if fb_resp.status == 200 and fb_resp.data:
            feedback_text = fb_resp.data.get("text")

        return render(
            request,
            "web/project_detail_customer.html",
            {"project": project, "form": form, "feedback_text": feedback_text, "has_translated_file": has_translated_file},
        )

    res: BackendResponse = backend_reject_project(project_id=str(project_id), text=text, token=str(token))
    if res.status in (200, 204):
        messages.success(request, _("Rejected and feedback sent"))
        return redirect("projects")

    detail: str | None = (res.data or {}).get("detail") or _("Failed to reject")
    messages.error(request, str(detail))
    return redirect("project_detail_customer", project_id=project_id)


def project_detail_admin_view(request: HttpRequest, project_id: str) -> HttpResponse:
    """Administrator detail view.

    Allows sending a message to customer/translator and closing the project.
    """
    try:
        _require_roles(request, {"ADMINISTRATOR"})
    except PermissionError:
        messages.error(request, _("Not allowed"))
        return redirect("login")

    token = _session(request).get(settings.SESSION_JWT_KEY)
    if not token:
        messages.error(request, _("Not authenticated"))
        return redirect("login")

    resp: BackendResponse[list[AdminFeedbackProjectOut]] = admin_list_feedback_projects(token=str(token))
    if resp.status != 200 or resp.data is None:
        detail: str | None = (resp.data or {}).get("detail") or _("Failed to load project")
        messages.error(request, str(detail))
        return redirect("projects")

    project: AdminFeedbackProjectOut | None = next((p for p in resp.data if str(p.get("id")) == str(project_id)), None)
    if project is None:
        messages.error(request, _("Project not found"))
        return redirect("projects")

    form: AdminMessageForm = AdminMessageForm()

    if request.method == "POST":
        action: str = (request.POST.get("action") or "").lower()

        if action == "send":
            form = AdminMessageForm(request.POST)
            if form.is_valid():
                r: BackendResponse = admin_send_project_message(
                    project_id=str(project_id),
                    token=str(token),
                    to=form.cleaned_data["to"],
                    subject=form.cleaned_data["subject"],
                    text=form.cleaned_data["text"],
                )
                if r.status in (200, 204):
                    messages.success(request, _("Message sent"))
                    return redirect("project_detail_admin", project_id=project_id)

                detail = (r.data or {}).get("detail") or _("Failed to send message")
                messages.error(request, str(detail))
            else:
                messages.error(request, _("Please fix the form errors."))

        elif action == "close":
            r = admin_close_project(project_id=str(project_id), token=str(token))
            if r.status in (200, 204):
                messages.success(request, _("Project closed"))
                return redirect("projects")

            detail = (r.data or {}).get("detail") or _("Failed to close project")
            messages.error(request, str(detail))

        else:
            messages.error(request, _("Invalid action"))

    return render(request, "web/project_detail_admin.html", {"project": project, "form": form})


def otp_setup_view(request: HttpRequest) -> HttpResponse:
    """Enable OTP for the current user and display provisioning URI."""
    token = _session(request).get(settings.SESSION_JWT_KEY)
    if not token:
        messages.error(request, _("Not authenticated"))
        return redirect("login")

    resp: BackendResponse = backend_otp_enable(token=str(token))
    if resp.status == 200 and resp.data and resp.data.get("otpauth_uri"):
        return render(request, "web/otp_setup.html", {"otpauth_uri": resp.data.get("otpauth_uri")})

    detail: str | None = (resp.data or {}).get("detail") or _("Failed to enable OTP")
    messages.error(request, str(detail))
    return redirect("home")
