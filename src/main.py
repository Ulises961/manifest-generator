import click
import os
from pathlib import Path
from typing import Optional
from pipeline import run
from utils.file_utils import load_environment
import click_completion


@click.group()
def cli():
    pass

@cli.command()
@click.option('--interactive', '-i', is_flag=True, default=False, 
              help='Run in interactive mode to configure all options')
@click.option('--repository-path', '-r', type=click.Path(exists=True, file_okay=False, dir_okay=True),
              help='Path to the repository to scan')
@click.option('--skaffold-file', '-s', type=click.Path(exists=True, file_okay=True, dir_okay=False),
              help='Path to skaffold file (optional)')
@click.option('--llm-model', '-m', help='LLM model name for inference')
@click.option('--llm-endpoint', '-e', help='LLM endpoint URL')
@click.option('--llm-token', '-t', help='LLM API token')
@click.option('--embeddings-model', help='Sentence transformer model name')
@click.option('--embeddings-endpoint', help='Embeddings endpoint URL')
@click.option('--embeddings-token', help='Embeddings API token')
@click.option('--overrides-file', type=click.Path(exists=True, file_okay=True, dir_okay=False),
              help='Path to configuration overrides file')
def main(interactive: bool, repository_path: Optional[str], skaffold_file: Optional[str],
         llm_model: Optional[str], llm_endpoint: Optional[str], llm_token: Optional[str],
         embeddings_model: Optional[str], embeddings_endpoint: Optional[str], 
         embeddings_token: Optional[str], overrides_file: Optional[str]):
    """
    Microservices Manifest Generator CLI
    
    Generate Kubernetes manifests from microservices repositories using AI.
    """
    config = {}
    
    if interactive or not all([repository_path, llm_model or llm_endpoint]):
        config = interactive_setup(repository_path, skaffold_file, llm_model, 
                                 llm_endpoint, llm_token, embeddings_model,
                                 embeddings_endpoint, embeddings_token, overrides_file)
    else:
        config = {
            'repository_path': repository_path,
            'skaffold_file': skaffold_file,
            'llm_model': llm_model,
            'llm_endpoint': llm_endpoint,
            'llm_token': llm_token,
            'embeddings_model': embeddings_model,
            'embeddings_endpoint': embeddings_endpoint,
            'embeddings_token': embeddings_token,
            'overrides_file': overrides_file
        }
    
    # Load environment variables
    load_environment()

    # Set environment variables based on configuration
    set_environment_variables(config)
    
    # Import and run the pipeline
    run()

def interactive_setup(repository_path=None, skaffold_file=None, llm_model=None,
                     llm_endpoint=None, llm_token=None, embeddings_model=None,
                     embeddings_endpoint=None, embeddings_token=None, overrides_file=None):
    """Interactive setup for configuration"""
    
    click.echo(click.style("🚀 Microservices Manifest Generator Setup", fg='blue', bold=True))
    click.echo("Let's configure your project step by step.\n")
    
    config = {}
    
    # Repository path (required)
    config['repository_path'] = repository_path or click.prompt(
        "📁 Path to repository to scan",
        type=click.Path(exists=True, file_okay=False, dir_okay=True),
        show_default=False
    )
    
    # Skaffold file (optional)
    if not skaffold_file:
        use_skaffold = click.confirm("📋 Do you have a Skaffold file to use?", default=False)
        if use_skaffold:
            config['skaffold_file'] = click.prompt(
                "📋 Path to Skaffold file",
                type=click.Path(exists=True, file_okay=True, dir_okay=False),
                show_default=False
            )
        else:
            config['skaffold_file'] = None
    else:
        config['skaffold_file'] = skaffold_file
    
    # LLM Configuration
    click.echo(click.style("\n🤖 LLM Configuration", fg='green', bold=True))
    
    if not llm_endpoint:
        llm_type = click.prompt(
            "Choose LLM setup",
            type=click.Choice(['local', 'openai', 'custom'], case_sensitive=False),
            default='local',
            show_choices=True
        )
        
        if llm_type == 'local':
            config['llm_endpoint'] = click.prompt(
                "🌐 LLM endpoint URL",
                default="http://localhost:8000/v1/chat/completions"
            )
            config['llm_model'] = llm_model or click.prompt(
                "🎯 LLM model name",
                default="codellama/CodeLlama-13b-Instruct-hf"
            )
            config['llm_token'] = llm_token or click.prompt(
                "🔑 LLM API token (optional)",
                default="",
                show_default=False
            )
        elif llm_type == 'openai':
            config['llm_endpoint'] = "https://api.openai.com/v1/chat/completions"
            config['llm_model'] = llm_model or click.prompt(
                "🎯 OpenAI model name",
                default="gpt-3.5-turbo"
            )
            config['llm_token'] = llm_token or click.prompt(
                "🔑 OpenAI API key",
                hide_input=True
            )
        else:  # custom
            config['llm_endpoint'] = llm_endpoint or click.prompt("🌐 Custom LLM endpoint URL")
            config['llm_model'] = llm_model or click.prompt("🎯 Model name")
            config['llm_token'] = llm_token or click.prompt(
                "🔑 API token (optional)",
                default="",
                show_default=False
            )
    else:
        config['llm_endpoint'] = llm_endpoint
        config['llm_model'] = llm_model or click.prompt("🎯 LLM model name")
        config['llm_token'] = llm_token or click.prompt(
            "🔑 LLM API token (optional)",
            default="",
            show_default=False
        )
    
    # Embeddings Configuration
    click.echo(click.style("\n🔍 Embeddings Configuration", fg='yellow', bold=True))
    
    if not embeddings_endpoint:
        embeddings_type = click.prompt(
            "Choose embeddings setup",
            type=click.Choice(['local', 'openai', 'custom'], case_sensitive=False),
            default='local',
            show_choices=True
        )
        
        if embeddings_type == 'local':
            config['embeddings_model'] = embeddings_model or click.prompt(
                "📊 Sentence transformer model name",
                default="all-MiniLM-L6-v2"
            )
            config['embeddings_endpoint'] = None
            config['embeddings_token'] = None
        elif embeddings_type == 'openai':
            config['embeddings_endpoint'] = "https://api.openai.com/v1/embeddings"
            config['embeddings_model'] = embeddings_model or click.prompt(
                "📊 OpenAI embeddings model",
                default="text-embedding-ada-002"
            )
            config['embeddings_token'] = embeddings_token or click.prompt(
                "🔑 OpenAI API key",
                hide_input=True
            )
        else:  # custom
            config['embeddings_endpoint'] = embeddings_endpoint or click.prompt("🌐 Custom embeddings endpoint URL")
            config['embeddings_model'] = embeddings_model or click.prompt("📊 Embeddings model name")
            config['embeddings_token'] = embeddings_token or click.prompt(
                "🔑 API token (optional)",
                default="",
                show_default=False
            )
    else:
        config['embeddings_endpoint'] = embeddings_endpoint
        config['embeddings_model'] = embeddings_model or click.prompt("📊 Embeddings model name")
        config['embeddings_token'] = embeddings_token or click.prompt(
            "🔑 Embeddings API token (optional)",
            default="",
            show_default=False
        )
    
    # Overrides file (optional)
    if not overrides_file:
        use_overrides = click.confirm("\n⚙️  Do you have a configuration overrides file?", default=False)
        if use_overrides:
            config['overrides_file'] = click.prompt(
                "⚙️  Path to overrides file",
                type=click.Path(exists=True, file_okay=True, dir_okay=False)
            )
        else:
            config['overrides_file'] = None
    else:
        config['overrides_file'] = overrides_file
    
    # Summary
    click.echo(click.style("\n✅ Configuration Summary:", fg='green', bold=True))
    click.echo(f"📁 Repository: {config['repository_path']}")
    if config.get('skaffold_file'):
        click.echo(f"📋 Skaffold file: {config['skaffold_file']}")
    click.echo(f"🤖 LLM Model: {config['llm_model']}")
    click.echo(f"🌐 LLM Endpoint: {config['llm_endpoint']}")
    click.echo(f"📊 Embeddings Model: {config['embeddings_model']}")
    if config.get('embeddings_endpoint'):
        click.echo(f"🔍 Embeddings Endpoint: {config['embeddings_endpoint']}")
    if config.get('overrides_file'):
        click.echo(f"⚙️  Overrides file: {config['overrides_file']}")
    
    if not click.confirm("\nProceed with this configuration?", default=True):
        click.echo("Setup cancelled.")
        raise click.Abort()
    
    return config

def set_environment_variables(config):
    """Set environment variables based on configuration"""
    
    # Required variables
    os.environ['TARGET_REPOSITORY'] = config['repository_path']
    os.environ['PRODUCTION_INFERENCE_MODEL'] = config['llm_model']
    os.environ['LLM_ENDPOINT'] = config['llm_endpoint']
    os.environ['EMBEDDINGS_MODEL'] = config['embeddings_model']
    
    # Optional variables
    if config.get('llm_token'):
        os.environ['LLM_API_KEY'] = config['llm_token']
    
    if config.get('embeddings_endpoint'):
        os.environ['EMBEDDINGS_ENDPOINT'] = config['embeddings_endpoint']
    
    if config.get('embeddings_token'):
        os.environ['EMBEDDINGS_API_KEY'] = config['embeddings_token']
    
    if config.get('overrides_file'):
        os.environ['OVERRIDES_FILE_PATH'] = config['overrides_file']
    
    # Set default paths if not already set
    if 'TARGET_PATH' not in os.environ:
        os.environ['TARGET_PATH'] = 'target'
    
    if 'MANIFESTS_PATH' not in os.environ:
        os.environ['MANIFESTS_PATH'] = 'manifests'
    
    if 'LLM_MANIFESTS_PATH' not in os.environ:
        os.environ['LLM_MANIFESTS_PATH'] = 'llm'

cli.add_command(main)

@cli.command()
def install_completion():
    """Print shell completion script for your shell."""
    click_completion.init()
    shell = click_completion.get_auto_shell()
    click.echo(click_completion.get_code(shell, 'python -m src.main'))

if __name__ == '__main__':
    cli()