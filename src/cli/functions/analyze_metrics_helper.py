
from typing import Any, Dict


from utils.file_utils import load_json_file, load_csv_file, save_json
from utils.logging_utils import setup_logging
import logging
import os

logger = logging.getLogger(__name__)

def run_analyze_metrics():
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

    repositories = [
        repo
        for repo in os.listdir(target_repository)
        if (os.path.isdir(os.path.join(target_repository, repo)))
    ]
    repositories.sort()
    logger.info(f"Found {len(repositories)} repositories")
    data = {"without_ir": {}, "with_ir": {}, "with_ir_corrected": {}, "with_overrides": {}, "with_overrides_corrected": {}}

    for repo in repositories:
        logging.info(f"Reviewing manifests for repository... {repo}")
        no_ir_results = os.path.join(
            target_repository,
            repo,
            "without-ir",
            os.getenv("RESULTS", "results"),
        )
        data["without_ir"][repo] = collect_data(no_ir_results)


        ir_results = os.path.join(
            target_repository,
            repo,
            "with-ir",
            os.getenv("RESULTS", "results"),
        )
        data["with_ir"][repo] = collect_data(ir_results)

        ir_corrected_results = os.path.join(
            target_repository,
            repo,
            "with-ir-corrected",
            os.getenv("RESULTS", "results"),
        )
        data["with_ir_corrected"][repo] = collect_data(ir_corrected_results)

        overrides_results = os.path.join(
            target_repository,
            repo,
            "with-overrides",
            os.getenv("RESULTS", "results"),
        )
        if os.path.exists(overrides_results):
            data.setdefault("with_overrides", {})
            data["with_overrides"][repo] = collect_data(overrides_results)

        overrides_corrected_results = os.path.join(
            target_repository,
            repo,
            "with-overrides-corrected",
            os.getenv("RESULTS", "results"),
        )
        if os.path.exists(overrides_corrected_results):
            data.setdefault("with_overrides_corrected", {})
            data["with_overrides_corrected"][repo] = collect_data(overrides_corrected_results)

    reporting = os.path.join(
        target_repository,"..", "Analysis", "results"
    )

    os.makedirs(reporting, exist_ok=True)

    save_json(data, os.path.join(reporting, "combined_metrics.json"))

    logger.info(f"Saved combined metrics to {os.path.join(reporting, 'combined_metrics.json')}")
    
    logger.info("Done")

def collect_data(path:str) -> Dict[str, Any]:
    data = {"skaffold": {}, "kubescape": 0}

    skaffold = load_json_file(os.path.join(path, "skaffold_validation_results.json"))

    data["skaffold"] = {
            "manifests_renderable": skaffold.get("dry_run_results", {}).get("success", False),
            "deployment_successful": skaffold.get("deployment_results", {}).get("success", False),
            "pods_ready": skaffold.get("service_health_checks", {}).get("pods_ready", False),
            "services_accessible": skaffold.get("service_health_checks", {}).get("services_accessible", False)
    }

    kubescape = load_csv_file(os.path.join(path, "validation_results.csv"))
    data["kubescape"] = analyze_kubescape_results(kubescape)

    llm_report = {}
    human_effort = None
    diff = []
    if os.path.exists(os.path.join(path, "llm_review_results.json")):
        llm_report = load_json_file(os.path.join(path, "llm_review_results.json"))
        data["llm_report"] = llm_report

    if os.path.exists(os.path.join(path, "diff_report.json")):
        diff = load_json_file(os.path.join(path, "diff_report.json"))
        if diff:
            human_effort = {
                "levenshtein_similarity":  diff.get("levenshtein_similarity", 0),
                "added_lines":  diff.get("detailed_report", {}).get("additions", 0),
                "removed_lines":  diff.get("detailed_report", {}).get("removals", 0),
                "modified_lines":  diff.get("detailed_report", {}).get("modifications", 0),
                "items": diff.get("details", []),
                "total_operations":  diff.get("total_operations", 0),
                "resources_affected":  diff.get("resources_affected", 0)
            }
            if "with-ir" in path:
                data["human_effort_ir"] = human_effort

    app = 0
    manual_review_path = os.path.join(os.getenv("ANALYSIS_REPOSITORY", ""), "results", "manually reviewed apps.csv")
    manual_review = load_csv_file(manual_review_path)

    without_ir_deploys = 1  # First "Deploys" column
    without_ir_behavior = 2  # First "Expected Behaviour" column
    
    with_ir_deploys = 3     # Second "Deploys" column  
    with_ir_behavior = 4    # Second "Expected Behaviour" column
    
    with_ir_corrected_deploys = 5     # Third "Deploys" column
    with_ir_corrected_behavior = 6    # Third "Expected Behaviour" column

    with_overrides_deploys = 7
    with_overrides_behaviour = 8

    with_overrides_corrected_deploys = 9
    with_overrides_corrected_behaviour = 10


    for row in manual_review[2:]:
        if "with-ir" in path and row[app] in path:
            # Only add manual review if deployment was successful
                data["manual_review"] = {
                    "deploys": row[with_ir_deploys] == "TRUE",
                    "expected_behaviour": row[with_ir_behavior] == "TRUE",
                }
            
        # Manual reviews were made for every app after corrections were applied
        elif "with-ir-corrected" in path and row[app] in path:
            data["manual_review"] = {
                "deploys": row[with_ir_corrected_deploys] == "TRUE",
                "expected_behaviour": row[with_ir_corrected_behavior] == "TRUE",
            }
        elif "without-ir" in path and row[app] in path:
            data["manual_review"] = {
                "deploys": row[without_ir_deploys] == "TRUE",
                "expected_behaviour": row[without_ir_behavior] == "TRUE",
            }
        elif "with_overrides" in path and row[app] in path:
            data["manual_review"] = {
                "deploys": row[with_overrides_deploys] == "TRUE",
                "expected_behaviour": row[with_overrides_behaviour] == "TRUE",
            }
        elif "with_overrides_corrected" in path and row[app] in path:
            data["manual_review"] = {
                "deploys": row[with_overrides_corrected_deploys] == "TRUE",
                "expected_behaviour": row[with_overrides_corrected_behaviour] == "TRUE"
            }

    return data
def analyze_kubescape_results( kubescape_results: list[list[str]]) -> Dict[str, int]:
    """
    Count the issues in the kubescape results and return a summary.
    """
    summary = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "total_controls": 0
    }

    header = kubescape_results[0]
    critical = header.index("critical")
    high = header.index("high")
    medium = header.index("medium")
    low = header.index("low")
    total_controls_per_manifests = header.index("total_controls")
    for resource in kubescape_results[1:]:
        summary["critical"] += int(resource[critical])
        summary["high"] += int(resource[high])
        summary["medium"] += int(resource[medium])
        summary["low"] += int(resource[low])
        summary["total_controls"] += int(resource[total_controls_per_manifests])
    return summary