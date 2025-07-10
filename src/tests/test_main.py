import pytest
from click.testing import CliRunner
from unittest.mock import patch
from main import cli
import tempfile
import shutil
import os

@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def temp_workspace():
    # Setup: create temporary workspace
    temp_dir = tempfile.mkdtemp()
    
    # Create necessary directories and files
    repo_dir = os.path.join(temp_dir, "repo")
    os.makedirs(repo_dir)
    
    config_file = os.path.join(temp_dir, "config.json")
    with open(config_file, 'w') as f:
        f.write("""
        {
            "repository_path": "%s",
            "llm_model": "model_name",
            "llm_endpoint": "http://localhost:8000/v1/chat/completions",
            "llm_token": "your_token",
            "embeddings_model": "all-MiniLM-L6-v2"
        }
        """ % repo_dir)
    
    yield {
        'temp_dir': temp_dir,
        'repo_dir': repo_dir,
        'config_file': config_file
    }
    
    # Teardown: cleanup
    shutil.rmtree(temp_dir)

@patch('pipeline.run')
def test_main_with_config_file(mock_run, runner, temp_workspace):
    mock_run.return_value = None
    result = runner.invoke(cli, ['main', '--config-file', temp_workspace['config_file']])
    
    if result.exit_code != 0:
        print(f"Command output: {result.output}")
        print(f"Exception: {result.exception}")
    
    assert result.exit_code == 0

@patch('pipeline.run')
def test_main_missing_required_fields(mock_run, runner, tmp_path):
    # Create a real directory that exists
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    
    # Create a temporary config file with missing required fields
    config_file = tmp_path / "config.json"
    config_file.write_text(f"""
    {{
        "repository_path": "{repo_dir}"
    }}
    """)

    result = runner.invoke(cli, ['main', '--config-file', str(config_file)])
    
    # The command should fail due to missing required fields
    assert result.exit_code != 0
    # Check that the error message is in the output
    assert "❌ Missing required field in config" in result.output

def test_main_invalid_config_file(runner, tmp_path):
    # Create an invalid config file
    config_file = tmp_path / "config.json"
    config_file.write_text("{ invalid json }")

    result = runner.invoke(cli, ['main', '--config-file', str(config_file)])
    
    # The command should fail due to invalid JSON
    assert result.exit_code != 0
    # Check that the JSON parsing error message is in the output
    assert "❌ Error parsing config file" in result.output

@patch('pipeline.run')
def test_main_dry_run_mode(mock_run, runner, tmp_path):
    mock_run.return_value = None
    
    # Create a real repository directory for the test
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    
    result = runner.invoke(cli, [
        'main', 
        '--repository-path', str(repo_dir), 
        '--llm-model', 'model_name', 
        '--llm-endpoint', 'http://localhost:8000/v1/chat/completions',
        '--embeddings-model', 'all-MiniLM-L6-v2',
        '--dry-run'
    ])
    
    if result.exit_code != 0:
        print(f"Command output: {result.output}")
        print(f"Exception: {result.exception}")
    
    assert result.exit_code == 0

@patch('pipeline.run')
def test_main_verbose_mode(mock_run, runner, tmp_path):
    mock_run.return_value = None
    
    # Create a real repository directory for the test
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    
    result = runner.invoke(cli, [
        'main', 
        '--repository-path', str(repo_dir), 
        '--llm-model', 'model_name', 
        '--llm-endpoint', 'http://localhost:8000/v1/chat/completions',
        '--embeddings-model', 'all-MiniLM-L6-v2',
        '--verbose'
    ])
    
    if result.exit_code != 0:
        print(f"Command output: {result.output}")
        print(f"Exception: {result.exception}")
    
    assert result.exit_code == 0

@patch('pipeline.run')
def test_main_interactive_mode(mock_run, runner, tmp_path):
    mock_run.return_value = None
    
    # Create a real repository directory for the test
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    
    # Use input parameter to simulate user input for interactive mode
    inputs = [
        str(repo_dir),  # repository path
        'n',  # no skaffold file
        'local',  # LLM type
        '',  # default LLM endpoint
        '',  # default LLM model
        '',  # no LLM token
        'n',  # no dry run
        'n',  # no verbose
        'local',  # embeddings type
        '',  # default embeddings model
        'n',  # no overrides file
        'y'  # confirm configuration
    ]
    
    result = runner.invoke(cli, ['main', '--interactive'], input='\n'.join(inputs))
    
    if result.exit_code != 0:
        print(f"Command output: {result.output}")
        print(f"Exception: {result.exception}")
    
    assert result.exit_code == 0

@patch('pipeline.run')
def test_main_config_file_not_exists(mock_run, runner):
    """Test with a config file that doesn't exist"""
    result = runner.invoke(cli, ['main', '--config-file', '/nonexistent/config.json'])
    
    # Click should handle this and return exit code 2 for invalid argument
    assert result.exit_code == 2
    assert "does not exist" in result.output

@patch('pipeline.run')  
def test_main_repository_path_not_exists(mock_run, runner):
    """Test with a repository path that doesn't exist"""
    result = runner.invoke(cli, [
        'main',
        '--repository-path', '/nonexistent/repo',
        '--llm-model', 'model_name',
        '--llm-endpoint', 'http://localhost:8000/v1/chat/completions',
        '--embeddings-model', 'all-MiniLM-L6-v2'
    ])
    
    # Click should handle this and return exit code 2 for invalid argument
    assert result.exit_code == 2
    assert "does not exist" in result.output