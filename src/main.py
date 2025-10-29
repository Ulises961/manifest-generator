import click
from cli.commands import generate, analyze_metrics, review_manifests
from utils.cli_utils import setup_readline


@click.group()
def cli():
    """Microservices Manifest Generator CLI"""
    pass


# Register commands
cli.add_command(generate)
cli.add_command(analyze_metrics, name="analyze-metrics")
cli.add_command(review_manifests, name="review-manifests")


if __name__ == "__main__":
    setup_readline()
    cli()