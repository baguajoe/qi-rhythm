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
