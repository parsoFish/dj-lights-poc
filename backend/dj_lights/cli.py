"""``dj-lights`` CLI entry. Mirrors healarr's Click style."""

from __future__ import annotations

import click
import uvicorn


@click.group()
def main() -> None:
    """DJ Lights POC."""


@main.command()
@click.option("--host", default="0.0.0.0", show_default=True)
@click.option("--port", default=8000, show_default=True, type=int)
@click.option("--reload/--no-reload", default=False)
def serve(host: str, port: int, reload: bool) -> None:
    """Run the FastAPI server (engine + WS bridge)."""

    uvicorn.run(
        "dj_lights.server.app:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
    )


if __name__ == "__main__":
    main()
