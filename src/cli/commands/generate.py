import os
import sys
import json
import click
from pathlib import Path
from typing import Optional, List
from cli.functions.generate_helper import run_generation
from utils.cli_utils import interactive_setup, set_environment_variables


@click.command()
@click.option(
    "--config-file",
    "-c",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Path to a config file (optional)",
)
@click.option(
    "--interactive",
    "-i",
    is_flag=True,
    default=False,
    help="Run in interactive mode to configure all options",
)
@click.option(
    "--repository-path",
    "-r",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to the repository to scan",
)
@click.option(
    "--output-path",
    "-o",
    type=click.Path(exists=False, file_okay=False, dir_okay=True),
    help="Path to save generated manifests (default: current directory)",
)
@click.option("--llm-model", help="LLM model name for inference")
@click.option("--llm-token", "-t", help="LLM API token")
@click.option("--embeddings-model", help="Sentence transformer model name")
@click.option(
    "--overrides-file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Path to configuration overrides file",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Run in dry-run mode, generating only heuristics based manifests without LLM inference",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable verbose logging for detailed output",
)
@click.option(
    "--selected-repositories",
    help="Comma-separated list of services to review after manual corrections",
)
@click.option(
    "--cache-prompt",
    is_flag=True,
    default=None,
    help="Enable caching of prompts for faster subsequent runs",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    default=False,
    help="Force overwrite existing output directory",
)
def generate(
    config_file: Optional[str],
    interactive: bool,
    repository_path: Optional[str],
    output_path: Optional[str],
    llm_model: Optional[str],
    llm_token: Optional[str],
    embeddings_model: Optional[str],
    overrides_file: Optional[str],
    dry_run: bool = False,
    verbose=False,
    selected_repositories: Optional[List[str]] = None,
    cache_prompt: Optional[bool] = None,
    force: bool = False,
):
    """
    Microservices Manifest Generator CLI

    Generate Kubernetes manifests from microservices repositories using AI.
    """
    
    # Handle bash-like expansions
    if repository_path:
        repository_path = os.path.expanduser(repository_path)
        repository_path = os.path.expandvars(repository_path)
    
    if output_path:
        output_path = os.path.expanduser(output_path)
        output_path = os.path.expandvars(output_path)
    
    if overrides_file:
        overrides_file = os.path.expanduser(overrides_file)
        overrides_file = os.path.expandvars(overrides_file)
    
    # Check if output directory exists and handle force flag
    if output_path and os.path.exists(output_path) and not force:
        if not click.confirm(
            f"⚠️  Output directory '{output_path}' already exists. Overwrite?",
            default=False,
        ):
            click.echo("Operation cancelled.")
            sys.exit(1)
    
    config = {}
    if config_file is not None:
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
        
        required_fields = ["repository_path", "output_path"]
        for field in required_fields:
            if field not in config or not config[field]:
                click.echo(
                    click.style(
                        f"❌ Missing required field in config: {field}", fg="red"
                    )
                )
                sys.exit(1)
    
    elif interactive or not all([repository_path, (llm_model) or dry_run, output_path]):
        config = interactive_setup(
            repository_path,
            output_path,
            llm_model,
            llm_token,
            embeddings_model,
            overrides_file,
            dry_run,
            verbose,
            selected_repositories,
            cache_prompt,
            force=force,
        )
    else:
        config = {
            "repository_path": repository_path,
            "output_path": output_path,
            "llm_model": llm_model,
            "llm_token": llm_token,
            "embeddings_model": embeddings_model,
            "overrides_file": overrides_file,
            "dry_run": dry_run,
            "verbose": verbose,
            "selected_repositories": selected_repositories,
            "cache_prompt": cache_prompt,
            "force": force,
        }
    
    set_environment_variables(config)
    
    run_generation()