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
