"""URL configuration for the Django frontend.

The frontend provides a server-rendered UI and proxies file downloads from the
backend.
"""

from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

from web import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("languages/", views.languages_view, name="languages"),
    path("projects/", views.projects_view, name="projects"),
    path("projects/new/", views.create_project_view, name="create_project"),

    path("projects/<uuid:project_id>/", views.project_detail_translator_view, name="project_detail_translator"),
    path("projects/<uuid:project_id>/customer/", views.project_detail_customer_view, name="project_detail_customer"),
    path("projects/<uuid:project_id>/original/", views.project_original_proxy_view, name="project_original"),
    path("projects/<uuid:project_id>/translated/", views.project_translated_proxy_view, name="project_translated"),
    path("projects/<uuid:project_id>/approve/", views.project_approve_view, name="project_approve"),
    path("projects/<uuid:project_id>/reject/", views.project_reject_view, name="project_reject"),
    path("projects/admin/<uuid:project_id>/", views.project_detail_admin_view, name="project_detail_admin"),
    path("otp/setup/", views.otp_setup_view, name="otp_setup"),
]
