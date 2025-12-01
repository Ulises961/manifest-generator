
from utils.logging_utils import setup_logging
import logging
import os
from validation.manifests_validator import ManifestsValidator

logger = logging.getLogger(__name__)

def run_review_manifests_with_reference():
    """Review the generated manifests using the LLM for best practices, security, and correctness."""
    # Set up logging
    setup_logging(
        log_dir="src/logs",
        log_file_name="microservices_validation.log",
        max_size_mb=10,  # 10MB per file
        console_output=True,
        log_level=(
            logging.DEBUG
            if os.getenv("VERBOSE", "false").lower() == "true"
            else logging.INFO
        ),
    )

    logger.info("Starting review of generated manifests")

    manifests_validator = ManifestsValidator()
    target_repository = os.getenv("OUTPUT_DIR", "")
    os.makedirs(target_repository, exist_ok=True)
    ## Filter repositories if SELECTED_REPOSITORIES is set
    selected_repos = (
        [r.strip() for r in os.getenv("SELECTED_REPOSITORIES", "").split(",")]
        if os.getenv("SELECTED_REPOSITORIES", "") != ""
        else []
    )
    ## Iterate over all repositories in the output directory of the pipeline generated manifests
    repositories = [
        repo
        for repo in os.listdir(target_repository)
        if (
            os.path.isdir(os.path.join(target_repository, repo))
            and (repo in selected_repos if len(selected_repos) > 0 else True)
        )
    ]
    repositories.sort()
    logger.info(f"Found {len(repositories)} repositories: {repositories}")

    for repo in repositories:
        logging.info(f"Reviewing manifests for repository... {repo}")
        ## Iterate over all stages
        for stage in ["without-ir", "with-ir", "with-overrides"]:
            logging.info(f"Reviewing manifests for stage... {stage}")
            try:
                manifests_root = os.path.join(
                    target_repository,
                    repo,
                    stage,
                )

                ## Skip if manifests root does not exist
                if not os.path.exists(manifests_root):
                    logging.warning(
                        f"Manifests root path does not exist: {manifests_root}. Skipping."
                    )
                    continue

                
                reference_manifests_path = os.getenv("REFERENCE_MANIFESTS_PATH", "")
                
                manifests_path = os.path.join(
                    manifests_root,
                    os.getenv("MANIFESTS_PATH", "manifests"),
                )

                validation_results_path__not_reviewed = os.path.join(
                    manifests_root, os.getenv("RESULTS", "results")
                )

                os.makedirs(validation_results_path__not_reviewed, exist_ok=True)


                ## When reference manifests path is set, use it over corrected manifests
                logger.info(
                    f"Using reference manifests path from environment: {reference_manifests_path}"
                )

                ## Validate against reference manifests in repository
                reviewed_manifests_path = os.path.join(
                    reference_manifests_path, repo, "kubernetes-manifests"
                )

                ##  Save results in folder for generated manifests
                validation_results_path__reviewed = os.path.join(
                    target_repository, repo, stage, os.getenv("RESULTS", "results")
                )
                
                os.makedirs(validation_results_path__reviewed, exist_ok=True)
                logger.info(
                    f"Using reference manifests from {reviewed_manifests_path} for repository {repo}"
                )

                ## Validate against corrected manifests
                manifests_validator.levenshtein_manifests_distance(
                    manifests_path, reviewed_manifests_path
                )

            except Exception as e:
                logger.error(
                    f"Error during review of manifests for repository {repo} at stage {stage}: {e}",
                    exc_info=True,
                )
    logger.info("Done")
