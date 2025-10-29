import os
import glob
import sys
import Levenshtein
import click
from typing import Dict, Optional, List
from logging import getLogger
from utils.file_utils import load_environment
from validation.manifests_validator import ManifestsValidator

logger = getLogger(__name__)

def set_environment_variables(config: Dict[str, str]):
    """Set environment variables based on configuration with path expansion"""
    load_environment()
    ### Required variables ###
    os.environ["TARGET_REPOSITORY"] = os.path.expanduser(
        os.path.expandvars(config["repository_path"])
    )
    os.environ["OUTPUT_DIR"] = (
        f"{os.path.expanduser(os.path.expandvars(config.get("output_path", "output")))}"
    )

    ### DEFAULT variables ###
    os.environ["EMBEDDINGS_MODEL"] = config.get(
        "embeddings_model", "sentence-transformers/all-MiniLM-L6-v2"
    )

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
    os.environ["OVERRIDES_PATH"] = config.get("overrides_file", "")
    os.environ["DRY_RUN"] = str(config.get("dry_run", "false"))

    os.environ["VERBOSE"] = str(config.get("verbose", "false"))
    os.environ["ENABLE_CACHING"] = str(config.get("cache_prompt", "true")).lower()
    os.environ["RESULTS"] = config.get("results_path", "results")
    os.environ["SEVERITY_CONFIG"] = config.get(
        "severity_config", "resources/validation/severity_config.yaml"
    )

    os.environ["SELECTED_REPOSITORIES"] = str(config.get("selected_repositories", []))
    os.environ["ANALYSIS_REPOSITORY"] = config.get("analysis_repository", "")
    logger.debug("Environment values: {os.environ}")


try:
    import gnureadline as readline
    
    def path_completer(text, state):
        """Tab completion for file paths"""
        if "~" in text:
            text = os.path.expanduser(text)
        
        if os.path.isdir(text):
            text += "/*"
        elif not text.endswith("*"):
            text += "*"
        
        matches = glob.glob(text)
        
        formatted_matches = []
        for match in matches:
            if os.path.isdir(match):
                formatted_matches.append(match + "/")
            else:
                formatted_matches.append(match)
        
        try:
            return formatted_matches[state]
        except IndexError:
            return None
    
    def setup_readline():
        """Set up readline for tab completion"""
        readline.set_completer(path_completer)
        readline.parse_and_bind("tab: complete")
        
        try:
            readline.read_history_file()
        except FileNotFoundError:
            pass
    
    def save_readline_history():
        """Save readline history"""
        try:
            readline.write_history_file()
        except:
            pass
    
    READLINE_AVAILABLE = True
    
except ImportError:
    READLINE_AVAILABLE = False
    
    def setup_readline():
        pass
    
    def save_readline_history():
        pass




def interactive_setup(
    repository_path=None,
    output_path=None,
    llm_model=None,
    llm_token=None,
    embeddings_model=None,
    overrides_file=None,
    dry_run=False,
    verbose=False,
    selected_repositories: Optional[List[str]] = None,
    cache_prompt: Optional[bool] = None,
    force: bool = False,
):
    """Interactive setup for configuration with enhanced terminal support"""
    
    click.echo(
        click.style("🚀 Microservices Manifest Generator Setup", fg="blue", bold=True)
    )
    click.echo("Let's configure your project step by step.\n")
    
    if READLINE_AVAILABLE:
        click.echo(
            click.style(
                "💡 Tip: Use Tab for path completion, Ctrl+Left/Right to navigate, Up/Down for history",
                fg="cyan",
            )
        )
    else:
        click.echo(
            click.style(
                "💡 Tip: Use ~ for home directory and $VAR for environment variables",
                fg="cyan",
            )
        )
        click.echo(
            click.style(
                "⚠️  Install 'readline' package for better terminal experience: pip install readline",
                fg="yellow",
            )
        )
    
    config = {}
    
    # Repository path with enhanced input
    while True:
        if READLINE_AVAILABLE:
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
        
        expanded_repo = os.path.expanduser(os.path.expandvars(repo_input.strip()))
        
        if os.path.exists(expanded_repo) and os.path.isdir(expanded_repo):
            config["repository_path"] = expanded_repo
            break
        else:
            click.echo(
                click.style(f"❌ Directory '{expanded_repo}' does not exist.", fg="red")
            )
            repository_path = None
    
    # Output path with enhanced input
    while True:
        if READLINE_AVAILABLE:
            try:
                if output_path:
                    output_input = output_path
                else:
                    default_output = "./target"
                    output_input = (
                        input(
                            f"📂 Path to save generated manifests [{default_output}]: "
                        )
                        or default_output
                    )
            except (KeyboardInterrupt, EOFError):
                click.echo("\nOperation cancelled.")
                sys.exit(1)
        else:
            output_input = output_path or click.prompt(
                "📂 Path to save generated manifests",
                type=str,
                default="./output",
            )
        
        expanded_output = os.path.expanduser(os.path.expandvars(output_input.strip()))
        
        if os.path.exists(expanded_output) and not force:
            if click.confirm(
                f"⚠️  Directory '{expanded_output}' exists. Overwrite?", default=False
            ):
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
    
    # Overrides file (optional)
    if not overrides_file:
        use_overrides = click.confirm(
            "\n⚙️  Do you have a configuration overrides file?", default=False
        )
        if use_overrides:
            if READLINE_AVAILABLE:
                try:
                    overrides_input = input("⚙️  Path to overrides file: ")
                    expanded_overrides = os.path.expanduser(
                        os.path.expandvars(overrides_input.strip())
                    )
                    if os.path.exists(expanded_overrides) and os.path.isfile(
                        expanded_overrides
                    ):
                        config["overrides_file"] = expanded_overrides
                    else:
                        click.echo(
                            click.style(
                                f"❌ File '{expanded_overrides}' does not exist.",
                                fg="red",
                            )
                        )
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
        config["llm_token"] = ""
        config["llm_model"] = ""
    else:
        config["dry_run"] = False
    
    if not config.get("dry_run", False):
        # LLM Configuration
        click.echo(
            click.style(
                "\n🤖 LLM Configuration - Anthropic only", fg="green", bold=True
            )
        )
        config["llm_model"] = llm_model or click.prompt(
            "🎯 LLM model name", default="claude-3-5-haiku-20241022"
        )
        config["llm_token"] = llm_token or click.prompt(
            "🔑 LLM API token (optional)", default="", show_default=False
        )
        
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
        click.echo(f"💾 Caching Enabled: {config['cache_prompt']}")
    click.echo(f"🔍 Verbose Mode: {config['verbose']}")
    click.echo(f"🔄 Selected Repositories: {config['selected_repositories']}")
    
    if not click.confirm("\nProceed with this configuration?", default=True):
        click.echo("Setup cancelled.")
        raise click.Abort()
    
    save_readline_history()
    
    return config