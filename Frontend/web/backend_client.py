from __future__ import annotations

import json
import urllib.error
import urllib.request
import urllib.parse
from dataclasses import dataclass
from typing import Generic, Mapping, TypeVar, TypedDict, cast

from django.conf import settings


class ErrorDetail(TypedDict, total=False):
    detail: str


class TokenOut(TypedDict, total=False):
    access_token: str
    token_type: str
    user_id: str
    role: str


class TranslatorLanguagesOut(TypedDict, total=False):
    translator_id: str
    languages: list[str]


class ProjectOut(TypedDict, total=False):
    id: str
    customer_id: str
    translator_id: str
    language_code: str
    state: str


class ProjectListItemOut(TypedDict, total=False):
    id: str
    language_code: str
    original_file_name: str
    state: str
    created_at: str
    customer_id: str
    customer_name: str
    translator_id: str
    translator_name: str


class ProjectDetailOut(TypedDict, total=False):
    id: str
    customer_id: str
    translator_id: str
    language_code: str
    original_file_id: str
    translated_file_id: str
    state: str
    created_at: str
    feedback_id: str


class FeedbackOut(TypedDict, total=False):
    project_id: str
    text: str
    created_at: str


class AdminFeedbackProjectOut(TypedDict, total=False):
    id: str
    language_code: str
    state: str
    customer_id: str
    customer_name: str
    customer_email: str
    translator_id: str
    translator_name: str
    translator_email: str
    feedback_text: str
    created_at: str


T = TypeVar("T")


@dataclass(frozen=True)
class BackendResponse(Generic[T]):
    """Response wrapper returned from the backend client.

    Attributes:
        status: HTTP status code.
        data: Decoded JSON response body (if any).
    """

    status: int
    data: T | None


def _request_json(
    *,
    method: str,
    path: str,
    payload: Mapping[str, object] | None = None,
    token: str | None = None,
) -> BackendResponse[dict[str, object]]:
    """Send an HTTP request to the FastAPI backend and parse JSON dict response."""

    base: str = settings.BACKEND_API_BASE_URL.rstrip("/")
    url: str = f"{base}{path}"

    headers: dict[str, str] = {}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data: bytes | None = json.dumps(payload).encode("utf-8") if payload is not None else None

    req: urllib.request.Request = urllib.request.Request(url=url, data=data, headers=headers, method=method)

    def _parse_dict(raw_json: str) -> dict[str, object] | None:
        if not raw_json:
            return None
        parsed = json.loads(raw_json)
        if parsed is None:
            return None
        if not isinstance(parsed, dict):
            # backend pro některé endpointy vrací list; pro ty používej _request_json_list
            raise TypeError("Expected JSON object")
        return cast(dict[str, object], parsed)

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            return BackendResponse(status=resp.status, data=_parse_dict(raw))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8") if e.fp else ""
        try:
            data_dict = _parse_dict(raw)
        except Exception:
            data_dict = {"detail": raw or "HTTP error"}
        return BackendResponse(status=e.code, data=data_dict)


def _request_json_list(
    *,
    method: str,
    path: str,
    payload: Mapping[str, object] | None = None,
    token: str | None = None,
) -> BackendResponse[list[dict[str, object]]]:
    """Send an HTTP request and parse JSON list response."""

    base: str = settings.BACKEND_API_BASE_URL.rstrip("/")
    url: str = f"{base}{path}"

    headers: dict[str, str] = {}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data: bytes | None = json.dumps(payload).encode("utf-8") if payload is not None else None

    req: urllib.request.Request = urllib.request.Request(url=url, data=data, headers=headers, method=method)

    def _parse_list(raw_json: str) -> list[dict[str, object]] | None:
        if not raw_json:
            return None
        parsed = json.loads(raw_json)
        if parsed is None:
            return None
        if not isinstance(parsed, list):
            raise TypeError("Expected JSON array")
        # normalize: keep only dict items
        out: list[dict[str, object]] = []
        for item in parsed:
            if isinstance(item, dict):
                out.append(cast(dict[str, object], item))
        return out

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            return BackendResponse(status=resp.status, data=_parse_list(raw))
    except urllib.error.HTTPError as e:
        # pro list endpointy při chybě často přijde dict s detail; mapujeme to na None a necháme status
        return BackendResponse(status=e.code, data=None)


def _post_json(path: str, payload: Mapping[str, object]) -> BackendResponse[dict[str, object]]:
    return _request_json(method="POST", path=path, payload=payload)


def register_user(*, name: str, email_address: str, password: str, role: str) -> BackendResponse[dict[str, object]]:
    """Register a user on the backend.

    Args:
        name: Username.
        email_address: Email address.
        password: Plaintext password.
        role: Role string (CUSTOMER/TRANSLATOR).

    Returns:
        BackendResponse: Backend API response.
    """
    if role == "TRANSLATOR":
        path = "/users/translators/register"
    else:
        path = "/users/customers/register"

    return _post_json(
        path,
        {
            "name": name,
            "email_address": email_address,
            "password": password,
        },
    )


def login(*, username: str, password: str) -> BackendResponse[TokenOut | ErrorDetail]:
    """Log in using username/password and get a JWT token."""
    resp = _post_json(
        "/auth/login",
        {
            "username": username,
            "password": password,
        },
    )
    return BackendResponse(status=resp.status, data=cast(TokenOut | ErrorDetail | None, resp.data))


def otp_enable(*, token: str) -> BackendResponse[dict[str, object]]:
    """Enable OTP for the current user and return provisioning URI."""
    return _request_json(method="POST", path="/auth/otp/enable", payload={}, token=token)


def otp_login(*, username: str, otp: str) -> BackendResponse[TokenOut | ErrorDetail]:
    """Log in using OTP (TOTP) and get a JWT token."""
    resp = _post_json(
        "/auth/otp/login",
        {
            "username": username,
            "otp": otp,
        },
    )
    return BackendResponse(status=resp.status, data=cast(TokenOut | ErrorDetail | None, resp.data))


def list_translator_languages(*, translator_id: str, token: str) -> BackendResponse[TranslatorLanguagesOut | ErrorDetail]:
    """List languages configured for a translator."""
    resp = _request_json(
        method="GET",
        path=f"/users/translators/{translator_id}/languages",
        token=token,
    )
    return BackendResponse(status=resp.status, data=cast(TranslatorLanguagesOut | ErrorDetail | None, resp.data))


def add_translator_language(*, translator_id: str, language_code: str, token: str) -> BackendResponse[dict[str, object]]:
    """Add a translator language (idempotent)."""
    return _request_json(
        method="POST",
        path=f"/users/translators/{translator_id}/languages",
        payload={"language_code": language_code},
        token=token,
    )


def delete_translator_language(*, translator_id: str, language_code: str, token: str) -> BackendResponse[dict[str, object]]:
    """Remove a translator language."""
    return _request_json(
        method="DELETE",
        path=f"/users/translators/{translator_id}/languages/{language_code}",
        token=token,
    )


def create_project(*, language_code: str, file_name: str, file_bytes: bytes, content_type: str, token: str) -> BackendResponse[ProjectOut | ErrorDetail]:
    """Create a new project and upload original file using multipart/form-data."""
    base: str = settings.BACKEND_API_BASE_URL.rstrip("/")
    url: str = f"{base}/projects"

    boundary: str = "----PIAEFormBoundary7MA4YWxkTrZu0gW"

    def _part(name: str, value: str) -> bytes:
        return (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"{name}\"\r\n\r\n"
            f"{value}\r\n"
        ).encode("utf-8")

    def _file_part(name: str, filename: str, ctype: str, data: bytes) -> bytes:
        return (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\n"
            f"Content-Type: {ctype}\r\n\r\n"
        ).encode("utf-8") + data + b"\r\n"

    body: bytes = b"".join(
        [
            _part("language_code", language_code),
            _file_part("original_file", file_name, content_type, file_bytes),
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )

    headers: dict[str, str] = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Authorization": f"Bearer {token}",
    }

    req: urllib.request.Request = urllib.request.Request(url=url, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            parsed = json.loads(raw) if raw else None
            return BackendResponse(status=resp.status, data=parsed)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8") if e.fp else ""
        try:
            parsed = json.loads(raw) if raw else None
        except Exception:
            parsed = {"detail": raw or "HTTP error"}
        return BackendResponse(status=e.code, data=parsed)


def list_projects(*, token: str) -> BackendResponse[list[ProjectListItemOut]]:
    """List projects for the current user."""
    resp = _request_json_list(method="GET", path="/projects", token=token)
    return BackendResponse(status=resp.status, data=cast(list[ProjectListItemOut] | None, resp.data))


def download_project_original(*, project_id: str, token: str) -> tuple[int, bytes, dict[str, str]]:
    """Download original file bytes from backend.

    Args:
        project_id: Project UUID.
        token: JWT token.

    Returns:
        tuple[int, bytes, dict[str, str]]: (status, file_bytes, response_headers)
    """

    base: str = settings.BACKEND_API_BASE_URL.rstrip("/")
    url: str = f"{base}/projects/{project_id}/original"

    req: urllib.request.Request = urllib.request.Request(url=url, method="GET", headers={"Authorization": f"Bearer {token}"})

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            headers = {k: v for (k, v) in resp.headers.items()}
            return resp.status, data, headers
    except urllib.error.HTTPError as e:
        data = e.read() if e.fp else b""
        headers = {k: v for (k, v) in getattr(e, "headers", {}).items()} if getattr(e, "headers", None) else {}
        return e.code, data, headers


def download_project_translated(*, project_id: str, token: str) -> tuple[int, bytes, dict[str, str]]:
    """Download translated file bytes from backend.

    Args:
        project_id: Project UUID.
        token: JWT token.

    Returns:
        tuple[int, bytes, dict[str, str]]: (status, file_bytes, response_headers)
    """

    base: str = settings.BACKEND_API_BASE_URL.rstrip("/")
    url: str = f"{base}/projects/{project_id}/translated"

    req: urllib.request.Request = urllib.request.Request(url=url, method="GET", headers={"Authorization": f"Bearer {token}"})

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            headers = {k: v for (k, v) in resp.headers.items()}
            return resp.status, data, headers
    except urllib.error.HTTPError as e:
        data = e.read() if e.fp else b""
        headers = {k: v for (k, v) in getattr(e, "headers", {}).items()} if getattr(e, "headers", None) else {}
        return e.code, data, headers


def submit_translation(*, project_id: str, file_name: str, file_bytes: bytes, content_type: str, token: str) -> BackendResponse[dict[str, object]]:
    """Upload translated file using multipart/form-data."""
    base: str = settings.BACKEND_API_BASE_URL.rstrip("/")
    url: str = f"{base}/projects/{project_id}/translation"

    boundary: str = "----PIAEFormBoundaryTranslatorUpload"

    def _file_part(name: str, filename: str, ctype: str, data: bytes) -> bytes:
        return (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\n"
            f"Content-Type: {ctype}\r\n\r\n"
        ).encode("utf-8") + data + b"\r\n"

    body: bytes = b"".join(
        [
            _file_part("translated_file", file_name, content_type, file_bytes),
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )

    headers: dict[str, str] = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Authorization": f"Bearer {token}",
    }

    req: urllib.request.Request = urllib.request.Request(url=url, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            parsed = json.loads(raw) if raw else None
            return BackendResponse(status=resp.status, data=parsed)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8") if e.fp else ""
        try:
            parsed = json.loads(raw) if raw else None
        except Exception:
            parsed = {"detail": raw or "HTTP error"}
        return BackendResponse(status=e.code, data=parsed)


def approve_project(*, project_id: str, token: str, text: str = "") -> BackendResponse[dict[str, object]]:
    """Approve a completed project and optionally send feedback."""
    return _request_json(method="POST", path=f"/projects/{project_id}/approve", payload={"text": text}, token=token)


def reject_project(*, project_id: str, text: str, token: str) -> BackendResponse[dict[str, object]]:
    """Reject a completed project and send feedback."""
    return _request_json(method="POST", path=f"/projects/{project_id}/reject", payload={"text": text}, token=token)


def get_feedback_by_project(*, project_id: str, token: str) -> BackendResponse[FeedbackOut | ErrorDetail]:
    """Get feedback for a project."""
    resp = _request_json(method="GET", path=f"/feedback/projects/{project_id}", token=token)
    return BackendResponse(status=resp.status, data=cast(FeedbackOut | ErrorDetail | None, resp.data))


def get_project(*, project_id: str, token: str) -> BackendResponse[ProjectDetailOut | ErrorDetail]:
    """Get detailed information about a project."""
    resp = _request_json(method="GET", path=f"/projects/{project_id}", token=token)
    return BackendResponse(status=resp.status, data=cast(ProjectDetailOut | ErrorDetail | None, resp.data))


def admin_list_feedback_projects(*, token: str, state: str | None = None) -> BackendResponse[list[AdminFeedbackProjectOut]]:
    """List all projects with feedback (admin view)."""
    q: str = f"?state={state}" if state else ""
    resp = _request_json_list(method="GET", path=f"/projects/admin/feedback{q}", token=token)
    return BackendResponse(status=resp.status, data=cast(list[AdminFeedbackProjectOut] | None, resp.data))


def admin_send_project_message(*, project_id: str, token: str, to: str, subject: str, text: str) -> BackendResponse[dict[str, object]]:
    """Send a message regarding a project (admin action)."""
    return _request_json(
        method="POST",
        path=f"/projects/admin/projects/{project_id}/message",
        payload={"to": to, "subject": subject, "text": text},
        token=token,
    )


def admin_close_project(*, project_id: str, token: str) -> BackendResponse[dict[str, object]]:
    """Close a project (admin action)."""
    return _request_json(method="POST", path=f"/projects/admin/projects/{project_id}/close", token=token)
