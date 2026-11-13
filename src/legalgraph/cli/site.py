"""The browsable site: its data, the Astro build and a local server."""

import subprocess

import click

from legalgraph import site as graph_site
from legalgraph.cli.main import cli
from legalgraph.load import Sources


def site_data(sources: Sources) -> None:
    try:
        counts = graph_site.generate_data(sources)
    except graph_site.SiteError as error:
        raise click.ClickException(str(error)) from error
    summary = ", ".join(f"{count} {collection}" for collection, count in counts.items())
    click.echo(f"✔ Site data written to {graph_site.DATA_DIR} ({summary})")


@cli.command("generate-site")
@click.option("--data-only", is_flag=True, help="Write the data files only; skip the Astro build.")
@click.pass_obj
def generate_site(sources: Sources, data_only: bool) -> None:
    """Build the browsable site into site/dist, ready to serve (needs bun)."""
    site_data(sources)
    if data_only:
        return
    try:
        graph_site.bun("run", "build")
    except (graph_site.SiteError, subprocess.CalledProcessError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(f"✔ Site built in {graph_site.SITE_DIR / 'dist'}")


@cli.command("serve-site")
@click.option("--port", default=4321, show_default=True)
@click.option("--built", is_flag=True, help="Serve the built site (site/dist) instead of the dev server.")
@click.pass_obj
def serve_site(sources: Sources, port: int, built: bool) -> None:
    """Browse the graph locally. The dev server reloads on site changes; rerun after data changes."""
    site_data(sources)
    try:
        if built:
            graph_site.bun("run", "build")
            graph_site.bun("run", "preview", "--port", str(port))
        else:
            graph_site.bun("run", "dev", "--port", str(port))
    except (graph_site.SiteError, subprocess.CalledProcessError) as error:
        raise click.ClickException(str(error)) from error
    except KeyboardInterrupt:
        pass
