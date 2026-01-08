from __future__ import annotations

import json
import urllib.error
import urllib.request
import urllib.parse
from dataclasses import dataclass
from typing import Any

from django.conf import settings


@dataclass(frozen=True)
class BackendResponse:
    """Response wrapper returned from the backend client.

    Attributes:
        status: HTTP status code.
        data: Decoded JSON response body (if any).
    """

    status: int
    data: dict[str, Any] | None


def _request_json(*, method: str, path: str, payload: dict[str, Any] | None = None, token: str | None = None) -> BackendResponse:
    """Send an HTTP request to the FastAPI backend and parse JSON response.

    This client uses only the Python standard library (urllib) to keep the Django
    frontend lightweight.

    Args:
        method: HTTP method.
        path: Backend path (starting with '/').
        payload: Optional JSON payload.
        token: Optional JWT access token.

    Returns:
        BackendResponse: Status code and parsed JSON body.
    """

    base = settings.BACKEND_API_BASE_URL.rstrip("/")
    url = f"{base}{path}"

    headers: dict[str, str] = {}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = json.dumps(payload).encode("utf-8") if payload is not None else None

    req = urllib.request.Request(url=url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
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


def _post_json(path: str, payload: dict[str, Any]) -> BackendResponse:
    return _request_json(method="POST", path=path, payload=payload)


def register_user(*, name: str, email_address: str, password: str, role: str) -> BackendResponse:
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


def login(*, username: str, password: str) -> BackendResponse:
    """Log in using username/password and get a JWT token."""
    return _post_json(
        "/auth/login",
        {
            "username": username,
            "password": password,
        },
    )


def otp_enable(*, token: str) -> BackendResponse:
    """Enable OTP for the current user and return provisioning URI."""
    return _request_json(method="POST", path="/auth/otp/enable", payload={}, token=token)


def otp_login(*, username: str, otp: str) -> BackendResponse:
    """Log in using OTP (TOTP) and get a JWT token."""
    return _post_json(
        "/auth/otp/login",
        {
            "username": username,
            "otp": otp,
        },
    )


def list_translator_languages(*, translator_id: str, token: str) -> BackendResponse:
    """List languages configured for a translator."""
    return _request_json(
        method="GET",
        path=f"/users/translators/{translator_id}/languages",
        token=token,
    )


def add_translator_language(*, translator_id: str, language_code: str, token: str) -> BackendResponse:
    """Add a translator language (idempotent)."""
    return _request_json(
        method="POST",
        path=f"/users/translators/{translator_id}/languages",
        payload={"language_code": language_code},
        token=token,
    )


def delete_translator_language(*, translator_id: str, language_code: str, token: str) -> BackendResponse:
    """Remove a translator language."""
    return _request_json(
        method="DELETE",
        path=f"/users/translators/{translator_id}/languages/{language_code}",
        token=token,
    )


def create_project(*, language_code: str, file_name: str, file_bytes: bytes, content_type: str, token: str) -> BackendResponse:
    """Create a new project and upload original file using multipart/form-data."""
    base = settings.BACKEND_API_BASE_URL.rstrip("/")
    url = f"{base}/projects"

    boundary = "----PIAEFormBoundary7MA4YWxkTrZu0gW"

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

    body = b"".join(
        [
            _part("language_code", language_code),
            _file_part("original_file", file_name, content_type, file_bytes),
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )

    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Authorization": f"Bearer {token}",
    }

    req = urllib.request.Request(url=url, data=body, headers=headers, method="POST")

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


def list_projects(*, token: str) -> BackendResponse:
    """List projects for the current user."""
    return _request_json(method="GET", path="/projects", token=token)


def download_project_original(*, project_id: str, token: str) -> tuple[int, bytes, dict[str, str]]:
    """Download original file bytes from backend.

    Args:
        project_id: Project UUID.
        token: JWT token.

    Returns:
        tuple[int, bytes, dict[str, str]]: (status, file_bytes, response_headers)
    """

    base = settings.BACKEND_API_BASE_URL.rstrip("/")
    url = f"{base}/projects/{project_id}/original"

    req = urllib.request.Request(url=url, method="GET", headers={"Authorization": f"Bearer {token}"})

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

    base = settings.BACKEND_API_BASE_URL.rstrip("/")
    url = f"{base}/projects/{project_id}/translated"

    req = urllib.request.Request(url=url, method="GET", headers={"Authorization": f"Bearer {token}"})

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            headers = {k: v for (k, v) in resp.headers.items()}
            return resp.status, data, headers
    except urllib.error.HTTPError as e:
        data = e.read() if e.fp else b""
        headers = {k: v for (k, v) in getattr(e, "headers", {}).items()} if getattr(e, "headers", None) else {}
        return e.code, data, headers


def submit_translation(*, project_id: str, file_name: str, file_bytes: bytes, content_type: str, token: str) -> BackendResponse:
    """Upload translated file using multipart/form-data."""
    base = settings.BACKEND_API_BASE_URL.rstrip("/")
    url = f"{base}/projects/{project_id}/translation"

    boundary = "----PIAEFormBoundaryTranslatorUpload"

    def _file_part(name: str, filename: str, ctype: str, data: bytes) -> bytes:
        return (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\n"
            f"Content-Type: {ctype}\r\n\r\n"
        ).encode("utf-8") + data + b"\r\n"

    body = b"".join(
        [
            _file_part("translated_file", file_name, content_type, file_bytes),
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )

    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Authorization": f"Bearer {token}",
    }

    req = urllib.request.Request(url=url, data=body, headers=headers, method="POST")

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


def approve_project(*, project_id: str, token: str, text: str = "") -> BackendResponse:
    """Approve a completed project and optionally send feedback."""
    return _request_json(method="POST", path=f"/projects/{project_id}/approve", payload={"text": text}, token=token)


def reject_project(*, project_id: str, text: str, token: str) -> BackendResponse:
    """Reject a completed project and send feedback."""
    return _request_json(method="POST", path=f"/projects/{project_id}/reject", payload={"text": text}, token=token)


def get_feedback_by_project(*, project_id: str, token: str) -> BackendResponse:
    """Get feedback for a project."""
    return _request_json(method="GET", path=f"/feedback/projects/{project_id}", token=token)


def get_project(*, project_id: str, token: str) -> BackendResponse:
    """Get detailed information about a project."""
    return _request_json(method="GET", path=f"/projects/{project_id}", token=token)


def admin_list_feedback_projects(*, token: str, state: str | None = None) -> BackendResponse:
    """List all projects with feedback (admin view)."""
    q = f"?state={state}" if state else ""
    return _request_json(method="GET", path=f"/projects/admin/feedback{q}", token=token)


def admin_send_project_message(*, project_id: str, token: str, to: str, subject: str, text: str) -> BackendResponse:
    """Send a message regarding a project (admin action)."""
    return _request_json(
        method="POST",
        path=f"/projects/admin/projects/{project_id}/message",
        payload={"to": to, "subject": subject, "text": text},
        token=token,
    )


def admin_close_project(*, project_id: str, token: str) -> BackendResponse:
    """Close a project (admin action)."""
    return _request_json(method="POST", path=f"/projects/admin/projects/{project_id}/close", token=token)
