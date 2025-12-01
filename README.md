# Microservices Manifest Generator

AI-powered tool for generating Kubernetes manifests from microservices repositories.

## Table of Contents
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Commands](#commands)
  - [generate](#generate)
  - [review-manifests](#review-manifests)
  - [review-manifests-with-reference](#review-manifests-with-reference)
  - [analyze-metrics](#analyze-metrics)
  - [analyze-especial-csvs](#analyze-especial-csvs)
- [Configuration](#configuration)
- [Examples](#examples)

## Installation

1. Clone the repository and navigate to its root:
   ```bash
   git clone <repository-url>
   cd Tool
   ```

2. Create a Python virtual environment:
   ```bash
   python3 -m venv .venv
   ```

3. Activate the virtual environment:
   ```bash
   source .venv/bin/activate
   ```

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Install the project as a package:
   ```bash
   pip install -e .
   ```

## Quick Start

### Basic Usage

Generate Kubernetes manifests from a microservices repository:

```bash
python src/main.py generate -c config.json
```

Or use interactive mode:

```bash
python src/main.py generate --interactive
```

## Commands

### generate

Generate Kubernetes manifests from microservices repositories using AI.

**Usage:**
```bash
python src/main.py generate [OPTIONS]
```

**Options:**
- `-c, --config-file PATH`: Path to configuration file (JSON)
- `-i, --interactive`: Run in interactive mode
- `-r, --repository-path PATH`: Path to the repository to scan
- `-o, --output-path PATH`: Path to save generated manifests
- `--llm-model TEXT`: LLM model name for inference
- `-t, --llm-token TEXT`: LLM API token
- `--embeddings-model TEXT`: Sentence transformer model name
- `--overrides-file PATH`: Path to configuration overrides file
- `--dry-run`: Generate heuristics-based manifests without LLM inference
- `-v, --verbose`: Enable verbose logging
- `--selected-repositories TEXT`: Comma-separated list of services to process
- `--cache-prompt`: Enable prompt caching for faster runs
- `-f, --force`: Force overwrite existing output directory

**Example:**
```bash
python src/main.py generate \
  -r /path/to/microservices-repo \
  -o /path/to/output \
  --llm-model claude-3-5-sonnet-20241022 \
  --llm-token YOUR_API_TOKEN \
  --verbose
```

### review-manifests

Review generated manifests using LLM for best practices, security, and correctness.

**Usage:**
```bash
python src/main.py review-manifests [OPTIONS]
```

**Options:**
- `-c, --config-file PATH`: Path to configuration file
- `-r, --results-path PATH`: Path to directory containing results to review
- `-p, --repositories TEXT`: Comma-separated repository paths
- `-v, --verbose`: Enable verbose logging
- `-d, --dry-run`: Run in dry-run mode

**Example:**
```bash
python src/main.py review-manifests -c config.json
```

### review-manifests-with-reference

Review generated manifests by comparing with human-authored reference manifests.

**Usage:**
```bash
python src/main.py review-manifests-with-reference [OPTIONS]
```

**Options:**
- `-c, --config-file PATH`: Path to configuration file
- `-r, --results-path PATH`: Path to directory containing results
- `-p, --repositories TEXT`: Comma-separated repository paths
- `-v, --verbose`: Enable verbose logging
- `-d, --dry-run`: Run in dry-run mode

**Example:**
```bash
python src/main.py review-manifests-with-reference -c config.json
```

**Output:**
- JSON report with detailed diff analysis
- CSV report with severity-classified issues
- Levenshtein similarity metrics

### analyze-metrics

Analyze and summarize metrics from generated manifests.

**Usage:**
```bash
python src/main.py analyze-metrics [OPTIONS]
```

**Options:**
- `-c, --config-file PATH`: Path to configuration file
- `-r, --results-path PATH`: Path to results directory
- `-p, --repositories TEXT`: Comma-separated repository paths
- `-v, --verbose`: Enable verbose logging

**Example:**
```bash
python src/main.py analyze-metrics -c config.json
```

### analyze-especial-csvs

Analyze severity reports from CSV files and generate consolidated metrics.

**Usage:**
```bash
python src/main.py analyze-especial-csvs [OPTIONS]
```

**Options:**
- `-c, --config-file PATH`: Path to configuration file
- `-r, --results-path PATH`: Path to results directory
- `-p, --repositories TEXT`: Comma-separated repository paths
- `-v, --verbose`: Enable verbose logging

**Example:**
```bash
python src/main.py analyze-especial-csvs -c config.json
```

**Output:**
- Formatted table showing severity distribution across repositories
- JSON file with aggregated metrics by repository and stage

## Configuration

### Config File Format

Create a `config.json` file with the following structure:

```json
{
  "repository_path": "/path/to/microservices/repo",
  "output_path": "/path/to/output",
  "llm_model": "claude-3-5-sonnet-20241022",
  "llm_token": "your-api-token",
  "embeddings_model": "all-MiniLM-L6-v2",
  "overrides_file": "/path/to/overrides.yaml",
  "dry_run": false,
  "verbose": true,
  "selected_repositories": "service1,service2,service3",
  "cache_prompt": true,
  "force": false,
  "target_repository": "/path/to/results",
  "use_reference_manifests": true,
  "reference_manifests_path": "/path/to/reference/manifests"
}
```

### Configuration Options

| Option | Description | Required |
|--------|-------------|----------|
| `repository_path` | Path to microservices repository | Yes (generate) |
| `output_path` | Output directory for manifests | Yes (generate) |
| `llm_model` | LLM model identifier | Yes (unless dry_run) |
| `llm_token` | API token for LLM service | Yes (unless dry_run) |
| `embeddings_model` | Sentence transformer model | No |
| `overrides_file` | YAML file with configuration overrides | No |
| `dry_run` | Generate without LLM inference | No |
| `verbose` | Enable detailed logging | No |
| `selected_repositories` | Comma-separated service names | No |
| `cache_prompt` | Enable prompt caching | No |
| `force` | Overwrite existing output | No |
| `target_repository` | Path to results for analysis | Yes (review/analyze) |
| `use_reference_manifests` | Use reference manifests for comparison | No |
| `reference_manifests_path` | Path to reference manifests | No |

### Environment Variables

The tool also supports environment variables (loaded from `.env` file):

```bash
# LLM Configuration
LLM_MODEL=claude-3-5-sonnet-20241022
LLM_TOKEN=your-api-token

# Embeddings
EMBEDDINGS_MODEL=all-MiniLM-L6-v2

# Paths
REPOSITORY_PATH=/path/to/repo
OUTPUT_DIR=/path/to/output
RESULTS=results

# Options
DRY_RUN=false
VERBOSE=true
CACHE_PROMPT=true
SELECTED_REPOSITORIES=service1,service2

# Reference Manifests
USE_REFERENCE_MANIFESTS=true
REFERENCE_MANIFESTS_PATH=/path/to/reference

# Severity Configuration
SEVERITY_CONFIG=resources/validation/severity_config.yaml
```

## Examples

### Example 1: Generate manifests with LLM

```bash
python src/main.py generate \
  --repository-path ~/microservices-demo \
  --output-path ~/output/demo \
  --llm-model claude-3-5-sonnet-20241022 \
  --llm-token sk-ant-... \
  --verbose
```

### Example 2: Generate without LLM (heuristics only)

```bash
python src/main.py generate \
  --repository-path ~/microservices-demo \
  --output-path ~/output/demo-heuristic \
  --dry-run
```

### Example 3: Review with reference manifests

```bash
python src/main.py review-manifests-with-reference \
  --config-file config.json \
  --verbose
```

### Example 4: Analyze severity metrics

```bash
python src/main.py analyze-especial-csvs \
  --results-path ~/Results \
  --repositories demo1,demo2,demo3 \
  --verbose
```

### Example 5: Interactive setup

```bash
python src/main.py generate --interactive
```

This will guide you through:
- Repository path selection
- Output directory configuration
- LLM model and token setup
- Additional options

## Output Structure

After running the tool, you'll get:

```
output/
├── <repository-name>/
│   ├── without-ir/           # Heuristics-based manifests
│   │   ├── manifests/
│   │   │   ├── service1-deployment.yaml
│   │   │   ├── service1-service.yaml
│   │   │   └── ...
│   │   ├── results/
│   │   │   ├── diff_report.json
│   │   │   ├── diff_report_with_reference.csv
│   │   │   └── skaffold_report.json
│   │   └── skaffold.yaml
│   ├── with-ir/              # LLM-enhanced manifests
│   └── with-overrides/       # Manifests with custom overrides
└── logs/
    └── *.log
```

## Troubleshooting

### Common Issues

1. **Module not found errors**: Ensure virtual environment is activated and dependencies installed
2. **API token errors**: Verify LLM_TOKEN is set correctly
3. **Path not found**: Use absolute paths or ensure relative paths are correct
4. **Permission errors**: Check file/directory permissions

### Debug Mode

Enable verbose logging for detailed output:

```bash
python src/main.py generate -c config.json --verbose
```

## Support

For issues, questions, or contributions, please refer to the project repository.