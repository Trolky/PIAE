from __future__ import annotations

from argparse import ArgumentParser
from typing import Any

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Run migrations and start the Django development server.

    This helper command is mainly used in Docker to ensure the SQLite database
    schema exists before starting the server.
    """

    help = "Run migrations and start development server (useful for Docker)."

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add command arguments."""
        parser.add_argument("addrport", nargs="?", default="0.0.0.0:8000")

    def handle(self, *args: Any, **options: Any) -> None:
        """Command entry point."""
        addrport: str = str(options.get("addrport", "0.0.0.0:8000"))
        self.stdout.write(self.style.NOTICE("Applying migrations..."))
        call_command("migrate", interactive=False)
        self.stdout.write(self.style.SUCCESS("Migrations applied."))
        self.stdout.write(self.style.NOTICE(f"Starting server on {addrport}..."))
        call_command("runserver", addrport)
