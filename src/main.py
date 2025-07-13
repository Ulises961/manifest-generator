import sys
import click
import os
from pathlib import Path
from typing import Any, Dict, Optional
from pipeline import run
from utils.file_utils import load_environment
import json


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
    '"llm_model": "model_name",'
    '"llm_endpoint": "http://localhost:8000/v1/chat/completions", '
    '"llm_token": "your_token", '
    '"embeddings_model": "sentence-transformers/all-MiniLM-L6-v2", '
    '"embeddings_endpoint": "http://localhost:8000/v1/embeddings", '
    '"embeddings_token": "your_embeddings_token", '
    '"overrides_file": "/path/to/overrides.json",'
    '"dry_run": false, '
    '"verbose": false, '
    '"overrides": "/path/to/overrides.yaml"'
    '"refinement_iterations": 3'
    '"output_path": "/path/to/produced/manifests"'
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
@click.option("--llm-model", help="LLM model name for inference")
@click.option("--llm-endpoint", help="LLM endpoint URL")
@click.option("--llm-token", "-t", help="LLM API token")
@click.option("--embeddings-model", help="Sentence transformer model name")
@click.option("--refinement-iterations", type=int, default=3)
@click.option("--embeddings-endpoint", help="Embeddings endpoint URL")
@click.option("--embeddings-token", help="Embeddings API token")
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
    is_flag=True,
    default=False,
    help="Enable verbose logging for detailed output",
)
def main(
    config_file: Optional[str],
    interactive: bool,
    repository_path: Optional[str],
    output_path: Optional[str],
    llm_model: Optional[str],
    llm_endpoint: Optional[str],
    llm_token: Optional[str],
    embeddings_model: Optional[str],
    embeddings_endpoint: Optional[str],
    embeddings_token: Optional[str],
    overrides_file: Optional[str],
    refinement_iterations: int = 3,
    dry_run: bool = False,
    verbose=False,
    cache_prompt: Optional[bool] = True,
):
    """
    Microservices Manifest Generator CLI

    Generate Kubernetes manifests from microservices repositories using AI.
    """

    # Load environment variables
    load_environment()

    config = {}
    if config_file is not None:
        # Load configuration from file
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
        required_fields = ["repository_path", "llm_model", "llm_endpoint"]
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
            (llm_endpoint, refinement_iterations, llm_model) or dry_run,
            output_path,
        ]
    ):
        config = interactive_setup(
            repository_path,
            output_path,
            llm_model,
            llm_endpoint,
            llm_token,
            embeddings_model,
            embeddings_endpoint,
            embeddings_token,
            overrides_file,
            refinement_iterations,
            dry_run,
            verbose,
            cache_prompt=cache_prompt,
        )
    else:
        config = {
            "repository_path": repository_path,
            "output_path": output_path,
            "llm_endpoint": llm_endpoint,
            "llm_model": llm_model,
            "llm_token": llm_token,
            "embeddings_model": embeddings_model,
            "embeddings_endpoint": embeddings_endpoint,
            "embeddings_token": embeddings_token,
            "overrides_file": overrides_file,
            "refinement_iterations": refinement_iterations,
            "dry_run": dry_run,
            "verbose": verbose,
            "cache_prompt": cache_prompt,
        }

    # Set environment variables based on configuration
    set_environment_variables(config)

    # Import and run the pipeline
    run()


def interactive_setup(
    repository_path=None,
    output_path=None,
    llm_model=None,
    llm_endpoint=None,
    llm_token=None,
    embeddings_model=None,
    embeddings_endpoint=None,
    embeddings_token=None,
    overrides_file=None,
    refinement_iterations=3,
    dry_run=False,
    verbose=False,
    cache_prompt: Optional[bool]= None,
):
    """Interactive setup for configuration"""

    click.echo(
        click.style("🚀 Microservices Manifest Generator Setup", fg="blue", bold=True)
    )
    click.echo("Let's configure your project step by step.\n")

    config = {}

    # Repository path (required)
    config["repository_path"] = repository_path or click.prompt(
        "📁 Path to repository to scan",
        type=click.Path(exists=True, file_okay=False, dir_okay=True),
        show_default=False,
    )

    # Output path (optional)
    config["output_path"] = output_path or click.prompt(
        "📂 Path to save generated manifests",
        type=click.Path(exists=False, file_okay=False, dir_okay=True),
        default="target",
    )

    # Embeddings Configuration
    click.echo(click.style("\n🔍 Embeddings Configuration", fg="yellow", bold=True))

    if not embeddings_endpoint:

        config["embeddings_model"] = embeddings_model or click.prompt(
            "📊 Sentence transformer model name", default="all-MiniLM-L6-v2"
        )
        config["embeddings_endpoint"] = None
        config["embeddings_token"] = None

    else:
        config["embeddings_endpoint"] = embeddings_endpoint
        config["embeddings_model"] = embeddings_model or click.prompt(
            "📊 Embeddings model name"
        )
        config["embeddings_token"] = embeddings_token or click.prompt(
            "🔑 Embeddings API token (optional)", default="", show_default=False
        )

    # Overrides file (optional)
    if not overrides_file:
        use_overrides = click.confirm(
            "\n⚙️  Do you have a configuration overrides file?", default=False
        )
        if use_overrides:
            config["overrides_file"] = click.prompt(
                "⚙️  Path to overrides file",
                type=click.Path(exists=True, file_okay=True, dir_okay=False),
            )
        else:
            config["overrides_file"] = None
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
        config["llm_endpoint"] = None
        config["llm_type"] = None
        config["llm_token"] = None
        config["llm_model"] = None
    else:
        config["dry_run"] = False

    if not config.get("dry_run", False):
        # LLM Configuration
        click.echo(click.style("\n🤖 LLM Configuration", fg="green", bold=True))

        if not llm_endpoint:
            llm_type = click.prompt(
                "Choose LLM setup",
                type=click.Choice(["local", "openai", "custom"], case_sensitive=False),
                default="local",
                show_choices=True,
            )

            if llm_type == "local":
                config["llm_endpoint"] = click.prompt(
                    "🌐 LLM endpoint URL",
                    default="http://localhost:8000/v1/chat/completions",
                )
                config["llm_model"] = llm_model or click.prompt(
                    "🎯 LLM model name", default="codellama/CodeLlama-13b-Instruct-hf"
                )
                config["llm_token"] = llm_token or click.prompt(
                    "🔑 LLM API token (optional)", default="", show_default=False
                )
            elif llm_type == "openai":
                config["llm_endpoint"] = "https://api.openai.com/v1/chat/completions"
                config["llm_model"] = llm_model or click.prompt(
                    "🎯 OpenAI model name", default="gpt-3.5-turbo"
                )
                config["llm_token"] = llm_token or click.prompt(
                    "🔑 OpenAI API key", hide_input=True
                )
            else:  # custom
                config["llm_endpoint"] = llm_endpoint or click.prompt(
                    "🌐 Custom LLM endpoint URL"
                )
                config["llm_model"] = llm_model or click.prompt("🎯 Model name")
                config["llm_token"] = llm_token or click.prompt(
                    "🔑 API token (optional)", default="", show_default=False
                )
        else:
            config["llm_endpoint"] = llm_endpoint
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
    if config.get("embeddings_endpoint"):
        click.echo(f"🔍 Embeddings Endpoint: {config['embeddings_endpoint']}")
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
        click.echo(f"🌐 LLM Endpoint: {config['llm_endpoint']}")
        click.echo(f"📊 Embeddings Model: {config['embeddings_model']}")
        click.echo(f"🔄 Refinement Iterations: {config['refinement_iterations']}")
        click.echo(f"💾 Caching Enabled: {config['cache_prompt']}")
    if not click.confirm("\nProceed with this configuration?", default=True):
        click.echo("Setup cancelled.")
        raise click.Abort()

    return config


def set_environment_variables(config: Dict[str, Any]):
    """Set environment variables based on configuration"""

    # Required variables
    os.environ["TARGET_REPOSITORY"] = config["repository_path"]

    os.environ["OUTPUT_DIR"] = config.get("output_path", "target")
    os.environ["EMBEDDINGS_MODEL"] = config["embeddings_model"]
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
    os.environ["MODELS_PATH"] = config.get("models_path", "resources/models")
    os.environ["MANUAL_MANIFESTS_PATH"] = config.get("manual_manifests_path", "manual")
    os.environ["K8S_MANIFESTS_PATH"] = config.get("k8s_manifests_path", "k8s")
    os.environ["LLM_MANIFESTS_PATH"] = config.get("llm_manifests_path", "llm")

    # Optional variables
    os.environ["LLM_API_KEY"] = config.get("llm_token", "")
    os.environ["EMBEDDINGS_ENDPOINT"] = config.get("embeddings_endpoint", "")
    os.environ["EMBEDDINGS_API_KEY"] = config.get("embeddings_token", "")
    os.environ["OVERRIDES_FILE_PATH"] = config.get("overrides_file", "")
    os.environ["REFINEMENT_ITERATIONS"] = str(config.get("refinement_iterations", 3))
    os.environ["DRY_RUN"] = str(config.get("dry_run", "false"))

    os.environ["VERBOSE"] = str(config.get("verbose", "false"))
    os.environ["ENABLE_CACHING"] = str(config.get("cache_prompt", "true")).lower()

cli.add_command(main)


if __name__ == "__main__":
    cli()