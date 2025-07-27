from calendar import c
import sys
import click
import os
from pathlib import Path
from typing import Any, Dict, Optional
from pipeline import run
from utils.file_utils import load_environment
import json
import gnureadline as readline
import glob
import logging

logger = logging.getLogger(__name__)


try:
    
    # Enable tab completion for file paths
    def path_completer(text, state):
        """Tab completion for file paths"""
        if '~' in text:
            text = os.path.expanduser(text)
        
        # Add wildcard if we're completing a directory
        if os.path.isdir(text):
            text += '/*'
        elif not text.endswith('*'):
            text += '*'
            
        matches = glob.glob(text)
        
        # Filter and format matches
        formatted_matches = []
        for match in matches:
            if os.path.isdir(match):
                formatted_matches.append(match + '/')
            else:
                formatted_matches.append(match)
        
        try:
            return formatted_matches[state]
        except IndexError:
            return None
    
    # Set up readline
    readline.set_completer(path_completer)
    readline.parse_and_bind("tab: complete")
    
    # Enable history
    try:
        readline.read_history_file()
    except FileNotFoundError:
        pass
    
    READLINE_AVAILABLE = True
except ImportError:
    READLINE_AVAILABLE = False


@click.group()
def cli():
    pass


@cli.command()
@click.option(
    "--config-file",
    "-c",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Path to a config file (optional) "
    "Shape: {"
    '"repository_path": "/path/to/repo", '
    '"output_path": "/path/to/produced/manifests",'
    '"llm_model": "model_name",'
    '"llm_token": "your_token", '
    '"embeddings_model": "sentence-transformers/all-MiniLM-L6-v2",'
    '"overrides_file": "/path/to/overrides.json",'
    '"dry_run": false, '
    '"verbose": false, '
    '"overrides": "/path/to/overrides.yaml"'
    '"refinement_iterations": 3'
    "}",
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
@click.option(
    "--llm-model", 
    help="LLM model name for inference"
)
@click.option("--llm-token", "-t", help="LLM API token")
@click.option("--embeddings-model", help="Sentence transformer model name")
@click.option("--refinement-iterations", type=int)
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
def main(
    config_file: Optional[str],
    interactive: bool,
    repository_path: Optional[str],
    output_path: Optional[str],
    llm_model: Optional[str],
    llm_token: Optional[str],
    embeddings_model: Optional[str],
    overrides_file: Optional[str],
    refinement_iterations: Optional[int],
    dry_run: bool = False,
    verbose=False,
    cache_prompt: Optional[bool] = None,
    force: bool = False,
):
    """
    Microservices Manifest Generator CLI

    Generate Kubernetes manifests from microservices repositories using AI.

    Examples:
        # Basic usage
        python main.py main -r ./my-repo -o ./output

        # Interactive mode
        python main.py main --interactive

        # Dry run with custom iterations
        python main.py main -r ./repo --dry-run --refinement-iterations 5

        # Force overwrite existing output
        python main.py main -r ./repo -o ./existing-output --force
    """

    # Load environment variables
    load_environment()

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
            default=False
        ):
            click.echo("Operation cancelled.")
            sys.exit(1)

    config = {}
    if config_file is not None:
        # Load configuration from file
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

        # Validate required fields
        required_fields = ["repository_path", "output_path"]
        for field in required_fields:
            if field not in config or not config[field]:
                click.echo(
                    click.style(
                        f"❌ Missing required field in config: {field}", fg="red"
                    )
                )
                sys.exit(1)

    elif interactive or not all(
        [
            repository_path,
            (refinement_iterations, llm_model) or dry_run,
            output_path,
        ]
    ):
        click.echo(f"{refinement_iterations},{cache_prompt}" )
        config = interactive_setup(
            repository_path,
            output_path,
            llm_model,
            llm_token,
            embeddings_model,
            overrides_file,
            refinement_iterations,
            dry_run,
            verbose,
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
            "refinement_iterations": refinement_iterations,
            "dry_run": dry_run,
            "verbose": verbose,
            "cache_prompt": cache_prompt,
            "force": force,
        }

    # Set environment variables based on configuration
    set_environment_variables(config)
    
    run()


def interactive_setup(
    repository_path=None,
    output_path=None,
    llm_model=None,
    llm_token=None,
    embeddings_model=None,
    overrides_file=None,
    refinement_iterations=None,
    dry_run=False,
    verbose=False,
    cache_prompt: Optional[bool]= None,
    force: bool = False,
):
    """Interactive setup for configuration with enhanced terminal support"""

    click.echo(
        click.style("🚀 Microservices Manifest Generator Setup", fg="blue", bold=True)
    )
    click.echo("Let's configure your project step by step.\n")
    
    if READLINE_AVAILABLE:
        click.echo(click.style("💡 Tip: Use Tab for path completion, Ctrl+Left/Right to navigate, Up/Down for history", fg="cyan"))
    else:
        click.echo(click.style("💡 Tip: Use ~ for home directory and $VAR for environment variables", fg="cyan"))
        click.echo(click.style("⚠️  Install 'readline' package for better terminal experience: pip install readline", fg="yellow"))

    config = {}

    # Repository path with enhanced input
    while True:
        if READLINE_AVAILABLE:
            # Use input() instead of click.prompt() for readline support
            try:
                if repository_path:
                    repo_input = repository_path
                else:
                    repo_input = input("📁 Path to repository to scan: ")
            except (KeyboardInterrupt, EOFError):
                click.echo("\nOperation cancelled.")
                sys.exit(1)
        else:
            repo_input = repository_path or click.prompt(
                "📁 Path to repository to scan",
                type=str,
                show_default=False,
            )
        
        # Expand paths
        expanded_repo = os.path.expanduser(os.path.expandvars(repo_input.strip()))
        
        if os.path.exists(expanded_repo) and os.path.isdir(expanded_repo):
            config["repository_path"] = expanded_repo
            break
        else:
            click.echo(click.style(f"❌ Directory '{expanded_repo}' does not exist.", fg='red'))
            repository_path = None

    # Output path with enhanced input
    while True:
        if READLINE_AVAILABLE:
            try:
                if output_path:
                    output_input = output_path
                else:
                    default_output = "./target"
                    output_input = input(f"📂 Path to save generated manifests [{default_output}]: ") or default_output
            except (KeyboardInterrupt, EOFError):
                click.echo("\nOperation cancelled.")
                sys.exit(1)
        else:
            output_input = output_path or click.prompt(
                "📂 Path to save generated manifests",
                type=str,
                default="./target",
            )
        
        expanded_output = os.path.expanduser(os.path.expandvars(output_input.strip()))
        
        if os.path.exists(expanded_output) and not force:
            if click.confirm(f"⚠️  Directory '{expanded_output}' exists. Overwrite?", default=False):
                config["output_path"] = expanded_output
                break
            else:
                output_path = None
        else:
            config["output_path"] = expanded_output
            break

    # Embeddings Configuration
    click.echo(click.style("\n🔍 Embeddings Configuration", fg="yellow", bold=True))

    config["embeddings_model"] = embeddings_model or click.prompt(
        "📊 Sentence transformer model name", default="all-MiniLM-L6-v2"
    )


    # Overrides file (optional) - use enhanced input for file paths
    if not overrides_file:
        use_overrides = click.confirm(
            "\n⚙️  Do you have a configuration overrides file?", default=False
        )
        if use_overrides:
            if READLINE_AVAILABLE:
                try:
                    overrides_input = input("⚙️  Path to overrides file: ")
                    expanded_overrides = os.path.expanduser(os.path.expandvars(overrides_input.strip()))
                    if os.path.exists(expanded_overrides) and os.path.isfile(expanded_overrides):
                        config["overrides_file"] = expanded_overrides
                    else:
                        click.echo(click.style(f"❌ File '{expanded_overrides}' does not exist.", fg='red'))
                        config["overrides_file"] = ""
                except (KeyboardInterrupt, EOFError):
                    config["overrides_file"] = ""
            else:
                config["overrides_file"] = click.prompt(
                    "⚙️  Path to overrides file",
                    type=click.Path(exists=True, file_okay=True, dir_okay=False),
                )
        else:
            config["overrides_file"] = ""
    else:
        config["overrides_file"] = overrides_file

    # Dry run option
    if dry_run or click.confirm(
        "\n🤖 Do you want to generate only heuristics based manifests (dry-run)?",
        default=False,
    ):
        config["dry_run"] = True
        click.echo(
            click.style(
                "ℹ️ Running in dry-run mode. No LLM inference will be performed.",
                fg="yellow",
            )
        )

        # Clear LLM related configurations        
        config["llm_token"] = ""
        config["llm_model"] = ""
        
    else:
        config["dry_run"] = False

    if not config.get("dry_run", False):
        # LLM Configuration
        click.echo(click.style("\n🤖 LLM Configuration - Anthropic only", fg="green", bold=True))
        config["llm_model"] = llm_model or click.prompt("🎯 LLM model name")
        config["llm_token"] = llm_token or click.prompt(
            "🔑 LLM API token (optional)", default="", show_default=False
        )

        # Refinement iterations
        if not refinement_iterations:
            config["refinement_iterations"] = click.prompt(
                "\n🔄 Number of refinement iterations",
                type=int,
                default=3,
                show_default=True,
            )
        else:
            config["refinement_iterations"] = refinement_iterations
        
        if not cache_prompt:
            config["cache_prompt"] = click.confirm(
                "\n💾 Enable caching of prompts for faster subsequent runs?",
                default=True,
            )
        else:
            config["cache_prompt"] = cache_prompt

    # Verbose mode
    if verbose or click.confirm(
        "\n🔍 Do you want to enable verbose logging?", default=False
    ):
        config["verbose"] = True
        click.echo(
            click.style(
                "🔍 Verbose mode enabled. Detailed logs will be printed.", fg="yellow"
            )
        )
    else:
        config["verbose"] = False

    # Summary
    click.echo(click.style("\n✅ Configuration Summary:", fg="green", bold=True))
    click.echo(f"📁 Repository: {config['repository_path']}")
    click.echo(f"📂 Output Path: {config['output_path']}")
    if config.get("overrides_file"):
        click.echo(f"⚙️  Overrides file: {config['overrides_file']}")
    if config.get("dry_run"):
        click.echo(
            click.style(
                "ℹ️ Running in dry-run mode. No LLM inference will be performed.",
                fg="yellow",
            )
        )
    else:
        click.echo(f"🤖 LLM Model: {config['llm_model']}")
        click.echo(f"🔑 LLM Token: {config['llm_token']}")
        click.echo(f"📊 Embeddings Model: {config['embeddings_model']}")
        click.echo(f"🔄 Refinement Iterations: {config['refinement_iterations']}")
        click.echo(f"💾 Caching Enabled: {config['cache_prompt']}")
    click.echo(f"🔍 Verbose Mode: {config['verbose']}")
    
    if not click.confirm("\nProceed with this configuration?", default=True):
        click.echo("Setup cancelled.")
        raise click.Abort()

    # Save readline history
    if READLINE_AVAILABLE:
        try:
            readline.write_history_file()
        except:
            pass
    
    return config


def set_environment_variables(config: Dict[str, str]):
    """Set environment variables based on configuration with path expansion"""

    ### Required variables ###
    os.environ["TARGET_REPOSITORY"] = os.path.expanduser(os.path.expandvars(config["repository_path"]))
    os.environ["OUTPUT_DIR"] = os.path.expanduser(os.path.expandvars(config.get("output_path", "target")))

    ### DEFAULT variables ###
    os.environ["EMBEDDINGS_MODEL"] = config.get("embeddings_model", "sentence-transformers/all-MiniLM-L6-v2")
    
    ### Knowledge base
    os.environ["SERVICES_PATH"] = config.get(
        "services_path", "resources/knowledge_base/microservices.json"
    )
    os.environ["SECRETS_PATH"] = config.get(
        "secrets_path", "resources/knowledge_base/secrets.json"
    )
    os.environ["VOLUMES_PATH"] = config.get(
        "volumes_path", "resources/knowledge_base/volumes.json"
    )
    os.environ["LABELS_PATH"] = config.get(
        "labels_path", "resources/knowledge_base/labels.json"
    )

    ## Templates
    os.environ["CONFIG_MAP_TEMPLATE_PATH"] = config.get(
        "configmap_template_path", "resources/k8s_templates/configmap.json"
    )
    os.environ["DEPLOYMENT_TEMPLATE_PATH"] = config.get(
        "deployment_template_path", "resources/k8s_templates/deployment.json"
    )
    os.environ["SERVICES_TEMPLATE_PATH"] = config.get(
        "service_template_path", "resources/k8s_templates/service.json"
    )
    os.environ["STATEFULSET_TEMPLATE_PATH"] = config.get(
        "statefulset_template_path", "resources/k8s_templates/statefulset.json"
    )
    os.environ["PVC_TEMPLATE_PATH"] = config.get(
        "pvc_template_path", "resources/k8s_templates/pvc.json"
    )

    ## Model path
    os.environ["MODELS_PATH"] = config.get("models_path", "resources/models")

    ## Paths for manifests
    os.environ["MANUAL_MANIFESTS_PATH"] = config.get("manual_manifests_path", "manual")
    os.environ["K8S_MANIFESTS_PATH"] = config.get("k8s_manifests_path", "k8s")
    os.environ["LLM_MANIFESTS_PATH"] = config.get("llm_manifests_path", "llm")

    ### Optional variables ###
    os.environ["LLM_MODEL"] = config.get("llm_model", "claude-3-5-haiku-latest")
    os.environ["LLM_API_KEY"] = config.get("llm_token", "")
    os.environ["OVERRIDES_FILE_PATH"] = config.get("overrides_file", "")
    os.environ["REFINEMENT_ITERATIONS"] = str(config.get("refinement_iterations", 3))
    os.environ["DRY_RUN"] = str(config.get("dry_run", "false"))

    os.environ["VERBOSE"] = str(config.get("verbose", "false"))
    os.environ["ENABLE_CACHING"] = str(config.get("cache_prompt", "true")).lower()
    os.environ["REVIEWED_MANIFESTS"] = config.get("reviewed_manifests_path", "final_manifests")
    os.environ["RESULTS"] = config.get("analysis_results_path", "results")
    os.environ["SEVERITY_CONFIG"] = config.get("severity_config", "resources/validation/severity_config.yaml")
    logger.debug("Environment values: {os.environ}")


cli.add_command(main)

if __name__ == "__main__":
    cli()