
from math import log
import re
from typing import Any, Dict


from utils.file_utils import load_json_file, load_csv_file, save_json
from utils.logging_utils import setup_logging
import logging
import os

logger = logging.getLogger(__name__)

def run_analyze_diffs():
    """Review the generated manifests using the LLM for best practices, security, and correctness."""
    # Set up logging
    setup_logging(
        log_dir="src/logs",
        log_file_name="metrics_preparation.log",
        max_size_mb=10,  # 10MB per file
        console_output=True,
        log_level=(
            logging.DEBUG
            if os.getenv("VERBOSE", "false").lower() == "true"
            else logging.INFO
        ),
    )

    logger.info("Starting review of generated manifests")

    target_repository = os.getenv("OUTPUT_DIR", "")

    ## Filter repositories if SELECTED_REPOSITORIES is set
    selected_repositories = [repo.strip() for repo in os.getenv("SELECTED_REPOSITORIES", "").split(",")]
    
    ## Iterate over all repositories in the output directory of the pipeline generated manifests
    repositories = [
        repo
        for repo in os.listdir(target_repository)
        if (os.path.isdir(os.path.join(target_repository, repo)))
        and (repo in selected_repositories)
    ]
    ## Sort repositories for consistent processing order
    repositories.sort()
    logger.info(f"Found {len(repositories)} repositories")

    ## Data structure to hold all collected data
    data = {"without_ir": {}, "with_ir": {}, "with_overrides": {}, }

    for repo in repositories:
        logging.info(f"Reviewing manifests for repository... {repo}")
        for stage in ["without-ir", "with-ir",  "with-overrides"]:
            logging.info(f"  Stage: {stage}")

            ## Collect data for <repo>/<stage>/results
            stage_results = os.path.join(
                target_repository,
                repo,
                stage,
                os.getenv("RESULTS", "results"),
            )
            data[stage.replace("-", "_")][repo] = collect_data(stage_results)
    logger.info("Completed data collection from all repositories")
    
    # Print data as a table
    print_data_table(data, repositories)
    
    reporting = os.path.join(
        target_repository,"..", "Analysis", "results"
    )

    os.makedirs(reporting, exist_ok=True)

    save_json(data, os.path.join(reporting, "combined_special_diff_metrics.json"))

    logger.info(f"Saved combined metrics to {os.path.join(reporting, 'combined_special_diff_metrics.json')}")
    
    logger.info("Done")

def print_data_table(data: Dict[str, Dict[str, Any]], repositories: list):
    """Print the collected data in a formatted table."""
    print("\n" + "="*120)
    print(" "*40 + "SEVERITY ANALYSIS SUMMARY")
    print("="*120)
    
    # Define severity order for consistent display
    severity_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
    
    for stage in ["without_ir", "with_ir", "with_overrides"]:
        if stage not in data:
            continue
            
        print(f"\n{'='*120}")
        print(f"Stage: {stage.upper().replace('_', ' ')}")
        print(f"{'='*120}")
        
        # Table header
        header = f"{'Repository':<25} | {'Total':<8} | " + " | ".join([f"{sev:<10}" for sev in severity_order])
        print(header)
        print("-"*120)
        
        # Table rows
        for repo in repositories:
            if repo not in data[stage]:
                continue
                
            repo_data = data[stage][repo]
            total_issues = repo_data.get("total_issues", 0)
            severity_counts = repo_data.get("severity", {})
            
            # Build row
            row_parts = [f"{repo:<25}", f"{total_issues:<8}"]
            for sev in severity_order:
                count = severity_counts.get(sev, 0)
                row_parts.append(f"{count:<10}")
            
            print(" | ".join(row_parts))
        
        # Calculate totals for this stage
        stage_totals = {"total": 0, "by_severity": {sev: 0 for sev in severity_order}}
        for repo in repositories:
            if repo in data[stage]:
                repo_data = data[stage][repo]
                stage_totals["total"] += repo_data.get("total_issues", 0)
                for sev, count in repo_data.get("severity", {}).items():
                    stage_totals["by_severity"][sev] = stage_totals["by_severity"].get(sev, 0) + count
        
        # Print totals row
        print("-"*120)
        totals_row = [f"{'TOTAL':<25}", f"{stage_totals['total']:<8}"]
        for sev in severity_order:
            count = stage_totals["by_severity"].get(sev, 0)
            totals_row.append(f"{count:<10}")
        print(" | ".join(totals_row))
    
    print("\n" + "="*120)

def collect_data(path: str) -> Dict[str, Any]:
    """
    Collect severity data from CSV report and structure it for analysis.
    
    Returns a dictionary with:
    - summary statistics (total issues, by severity, by stage)
    - detailed issues grouped by microservice
    - severity distribution
    """
    csv_path = os.path.join(path, "diff_report_with_reference.csv")
    
    if not os.path.exists(csv_path):
        logger.warning(f"CSV report not found: {csv_path}")
        return {}
    
    try:
        csv_data = load_csv_file(csv_path)
        
        # Skip header row
        header = csv_data[0]
        rows = csv_data[1:]
        
        # Initialize counters
        summary = {
            "total_issues": len(rows),
            "severity": {},
            "issues_by_severity": {},
        }
        
        microservices = {}
        
        for row in rows:
            if len(row) < 10:
                logger.warning(f"Skipping malformed row: {row}")
                continue
            
            issue = {
                "stage": row[0],
                "microservice": row[1],
                "issue_type": row[2],
                "path": row[3],
                "reference_value": row[4],
                "analyzed_value": row[5],
                "severity_level": row[6],
                "severity_description": row[7],
                "reviewed_level": row[8],
                "comments": row[9]
            }
            
            # Update summary counters
            severity = issue["severity_level"]
            reviewed = issue["reviewed_level"]

            if reviewed and reviewed != "":            
               summary["severity"][reviewed] = summary["severity"].get(reviewed, 0) + 1
               summary["issues_by_severity"][reviewed] = summary["issues_by_severity"].get(reviewed, [])
               summary["issues_by_severity"][reviewed].append(issue)
            else:
               summary["severity"][severity] = summary["severity"].get(severity, 0) + 1
               summary["issues_by_severity"][severity] = summary["issues_by_severity"].get(severity, [])   
               summary["issues_by_severity"][severity].append(issue)

        
       
        return {
             "total_issues": len(rows),
            "severity": summary["severity"],
            "issues_by_severity": summary["issues_by_severity"],
        }
        
    except Exception as e:
        logger.exception(f"Error processing CSV file {csv_path}: {e}")
        return {
            "severity": {},
            "issues_by_severity": {},
            "total_issues": 0           
        }
   