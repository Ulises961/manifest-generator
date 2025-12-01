import click
from cli.commands import (
    analyze_especial_csvs,
    generate,
    analyze_metrics,
    review_manifests,
    review_manifests_with_reference,
)

from utils.cli_utils import setup_readline


@click.group()
def cli():
    """Microservices Manifest Generator CLI"""
    pass


# Register commands
cli.add_command(generate)
cli.add_command(analyze_metrics, name="analyze-metrics")
cli.add_command(review_manifests, name="review-manifests")
cli.add_command(review_manifests_with_reference, name="review-manifests-with-reference")
cli.add_command(analyze_especial_csvs, name="analyze-especial-csvs")

if __name__ == "__main__":
    setup_readline()
    cli()
