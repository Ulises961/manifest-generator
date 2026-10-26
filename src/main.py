import click
from cli.commands.analyze_especial_csvs import analyze_especial_csvs
from cli.commands.generate import generate
from cli.commands.analyze_metrics import analyze_metrics
from cli.commands.review_manifests import review_manifests
from cli.commands.review_manifests_with_reference import review_manifests_with_reference

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
