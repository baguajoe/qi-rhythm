import click
from flask import Flask


def register_cli(app: Flask) -> None:
    @app.cli.command("seed")
    @click.option("--demo", is_flag=True, help="Also create a demo organization and instructor.")
    def seed_cmd(demo: bool):
        """Seed the bundled rhythm library (idempotent)."""
        from .seed import seed_demo, seed_library

        g, r = seed_library()
        click.echo(f"Seeded {g} genres and {r} rhythms.")
        if demo:
            inst = seed_demo()
            click.echo(f"Demo instructor: {inst.email}")

    @app.cli.command("purge-recordings")
    @click.option("--all", "purge_all", is_flag=True, help="Delete every recording now.")
    def purge_cmd(purge_all: bool):
        """Delete recordings past each organization's retention period (run daily)."""
        from .services.game import purge_recordings

        n = purge_recordings(older_than_days=None if purge_all else -1)
        click.echo(f"Deleted {n} recordings.")

    @app.cli.command("set-role")
    @click.argument("email")
    @click.argument("role", type=click.Choice(["instructor", "admin", "superadmin"]))
    def set_role_cmd(email: str, role: str):
        """Change an instructor's role. Super-admins manage the Qi Rhythm Library.

        This is the only way to grant super-admin: there is deliberately no API for it.
        """
        from .extensions import db
        from .models import Instructor

        inst = Instructor.query.filter_by(email=email.strip().lower()).one_or_none()
        if inst is None:
            raise click.ClickException(f"No instructor with email {email}.")
        old = inst.role
        inst.role = role
        db.session.commit()
        click.echo(f"{inst.email}: {old} -> {role}")
