import pytest
from click.testing import CliRunner
from unittest.mock import patch
from main import cli
import json

@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def temp_workspace(tmp_path):
    # Setup: create temporary workspace
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    
    config_file = tmp_path / "config.json"
    config_data = {
        "repository_path": str(repo_dir),
        "output_path": str(output_dir),
        "llm_model": "model_name",
        "llm_token": "your_token",
        "embeddings_model": "all-MiniLM-L6-v2"
    }
    config_file.write_text(json.dumps(config_data))
    
    return {
        'temp_dir': str(tmp_path),
        'repo_dir': str(repo_dir),
        'output_dir': str(output_dir),
        'config_file': str(config_file)
    }

@patch('cli.commands.generate.run_generation')
def test_main_with_config_file(mock_run, runner, temp_workspace):
    mock_run.return_value = None
    result = runner.invoke(cli, ['generate', '--config-file', temp_workspace['config_file']])
    
    if result.exit_code != 0:
        print(f"Command output: {result.output}")
        print(f"Exception: {result.exception}")
    
    assert result.exit_code == 0
    mock_run.assert_called_once()

@patch('cli.functions.generate_helper.run_generation')
def test_main_missing_required_fields(mock_run, runner, tmp_path):
    # Create a real directory that exists
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    
    # Create a temporary config file with missing required fields
    config_file = tmp_path / "config.json"
    config_data = {"repository_path": str(repo_dir)}
    config_file.write_text(json.dumps(config_data))

    result = runner.invoke(cli, ['generate', '--config-file', str(config_file)])
    
    # The command should fail due to missing required fields
    assert result.exit_code != 0
    # Check that the error message is in the output
    assert "❌ Missing required field in config" in result.output

def test_main_invalid_config_file(runner, tmp_path):
    # Create an invalid config file
    config_file = tmp_path / "config.json"
    config_file.write_text("{ invalid json }")

    result = runner.invoke(cli, ['generate', '--config-file', str(config_file)])
    
    # The command should fail due to invalid JSON
    assert result.exit_code != 0
    # Check that the JSON parsing error message is in the output
    assert "❌ Error parsing config file" in result.output

@patch('cli.commands.generate.run_generation')
@patch('cli.commands.generate.set_environment_variables')
def test_main_dry_run_mode(mock_set_env, mock_run, runner, tmp_path):
    mock_run.return_value = None
    mock_set_env.return_value = None
    
    # Create a real repository directory for the test
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    output_dir = tmp_path / "output"
    
    result = runner.invoke(cli, [
        'generate', 
        '--repository-path', str(repo_dir),
        '--output-path', str(output_dir),
        '--embeddings-model', 'all-MiniLM-L6-v2',
        '--dry-run'
    ])
    
    if result.exit_code != 0:
        print(f"Command output: {result.output}")
        print(f"Exception: {result.exception}")
    
    assert result.exit_code == 0
    mock_run.assert_called_once()

@patch('cli.commands.generate.run_generation')
@patch('cli.commands.generate.set_environment_variables')
def test_main_verbose_mode(mock_set_env, mock_run, runner, tmp_path):
    mock_run.return_value = None
    mock_set_env.return_value = None
    
    # Create a real repository directory for the test
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    output_dir = tmp_path / "output"
    
    result = runner.invoke(cli, [
        'generate', 
        '--repository-path', str(repo_dir),
        '--output-path', str(output_dir),
        '--llm-model', 'model_name',
        '--embeddings-model', 'all-MiniLM-L6-v2',
        '--verbose'
    ])
    
    if result.exit_code != 0:
        print(f"Command output: {result.output}")
        print(f"Exception: {result.exception}")
    
    assert result.exit_code == 0
    mock_run.assert_called_once()

@patch('cli.commands.generate.run_generation')
@patch('cli.commands.generate.set_environment_variables')
@patch('cli.commands.generate.interactive_setup')
def test_main_interactive_mode(mock_interactive, mock_set_env, mock_run, runner, tmp_path):
    mock_run.return_value = None
    mock_set_env.return_value = None
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    output_dir = tmp_path / "output"
    
    # Mock interactive_setup to return a valid config
    mock_interactive.return_value = {
        'repository_path': str(repo_dir),
        'output_path': str(output_dir),
        'llm_model': 'model_name',
        'embeddings_model': 'all-MiniLM-L6-v2',
        'dry_run': False,
        'verbose': False,
        'llm_token': None,
        'overrides_file': None,
        'selected_repositories': None,
        'cache_prompt': None,
        'force': False
    }
    
    result = runner.invoke(cli, ['generate', '--interactive'])
    
    if result.exit_code != 0:
        print(f"Command output: {result.output}")
        print(f"Exception: {result.exception}")
    
    assert result.exit_code == 0
    mock_interactive.assert_called_once()
    mock_run.assert_called_once()

def test_main_config_file_not_exists(runner):
    """Test with a config file that doesn't exist"""
    result = runner.invoke(cli, ['generate', '--config-file', '/nonexistent/config.json'])
    
    # Click should handle this and return exit code 2 for invalid argument
    assert result.exit_code == 2
    assert "does not exist" in result.output.lower() or "invalid value" in result.output.lower()

def test_main_repository_path_not_exists(runner):
    """Test with a repository path that doesn't exist"""
    result = runner.invoke(cli, [
        'generate',
        '--repository-path', '/nonexistent/repo',
        '--output-path', '/tmp/output',
        '--llm-model', 'model_name',
        '--embeddings-model', 'all-MiniLM-L6-v2'
    ])
    
    # Click should handle this and return exit code 2 for invalid argument
    assert result.exit_code == 2
    assert "does not exist" in result.output.lower() or "invalid value" in result.output.lower()