import json
import os
from pathlib import Path
import sys
import click
from typing import Optional

from cli.functions.analyze_metrics_helper import run_analyze_metrics
from utils.cli_utils import set_environment_variables


@click.command()
@click.option(
    "results_repository",
    "--results-path",
    "-r",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    required=False,
    help="Path to the directory containing the results to review",
)
@click.option(
    "selected_repositories",
    "--repositories",
    "-p",
    required=False,
    help="Comma separated paths to the repositories containing the manifests to review",
)
@click.option(
    "verbose",
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable verbose logging for detailed output",
)
@click.option(
    "config_file",
    "--config-file",
    "-c",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Path to a config file (optional)",
)

def analyze_metrics(
    results_repository: str,
    selected_repositories: Optional[str] = None,
    config_file: Optional[str] = None,
    dry_run: Optional[bool] = None,
    verbose: Optional[bool] = None,
):
    """Analyze the metrics and return a summary."""

    if not selected_repositories and not config_file:
        click.echo(
            click.style(
                "❌ You must provide both --selected-repositories or a --config-file",
                fg="red",
            )
        )
        sys.exit(1)
    
    config = {
        "target_repository": results_repository,
        "selected_repositories": selected_repositories,
        "dry_run": dry_run,
        "verbose": verbose,
    }
    
    if selected_repositories:
        config["selected_repositories"] = selected_repositories
    
    if config_file:
        config_file = os.path.expanduser(config_file)
        if not Path(config_file).is_file():
            click.echo(
                click.style(
                    f"❌ Error: Config file '{config_file}' does not exist.", fg="red"
                )
            )
            sys.exit(1)
        
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            click.echo(click.style(f"❌ Error parsing config file: {e}", fg="red"))
            sys.exit(1)
    
    set_environment_variables(config)
    run_analyze_metrics()