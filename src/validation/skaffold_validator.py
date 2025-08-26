import logging
import os
import subprocess
import time
import yaml
from typing import Dict, Any, List, Optional
import tempfile
import shutil


class SkaffoldValidator:
    """
    Validates Kubernetes manifests by attempting to deploy them using Skaffold.
    """
    
    def __init__(self, skaffold_path: str = "skaffold", timeout: int = 300):
        self.skaffold_path = skaffold_path
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
    
    def validate_cluster_deployment(self, manifests_path: str) -> Dict[str, Any]:
        """
        Validate cluster deployment using Skaffold dry-run and deployment test.
        
        Args:
            manifests_path: Path to the directory containing manifests and skaffold.yaml
            
        Returns:
            Dict containing validation results and metrics
        """
        results = {
            "manifests_path": manifests_path,
            "validation_timestamp": time.time(),
            "dry_run_results": {},
            "deployment_results": {},
            "service_health_checks": {},
            "overall_status": "unknown",
            "errors": [],
            "warnings": []
        }
        
        try:
            # 1. Validate Skaffold configuration
            config_valid = self._validate_skaffold_config(manifests_path)
            results["config_validation"] = config_valid
            
            if not config_valid["valid"]:
                results["overall_status"] = "failed"
                results["errors"].extend(config_valid["errors"])
                return results
            
            # 2. Run Skaffold dry-run (renders manifests without deploying)
            dry_run_results = self._run_skaffold_dry_run(manifests_path)
            results["dry_run_results"] = dry_run_results
            
            # 3. Optional: Actually deploy to a test namespace (if enabled)
            if os.getenv("ENABLE_ACTUAL_DEPLOYMENT", "true").lower() == "true":
                deploy_results = self._run_skaffold_deploy(manifests_path)
                results["deployment_results"] = deploy_results
                
                # 4. Run health checks on deployed services
                if deploy_results.get("success", False):
                    health_results = self._check_service_health(manifests_path)
                    results["service_health_checks"] = health_results
                    
                    # Clean up deployment
                    self._cleanup_deployment(manifests_path)
            
            # Determine overall status
            results["overall_status"] = self._determine_overall_status(results)
            
        except Exception as e:
            self.logger.error(f"Skaffold validation failed: {e}")
            results["overall_status"] = "error"
            results["errors"].append(str(e))
        
        return results
    
    def _validate_skaffold_config(self, manifests_path: str) -> Dict[str, Any]:
        """Validate the Skaffold configuration file."""
        skaffold_file = os.path.join(manifests_path, "skaffold.yaml")
        
        if not os.path.exists(skaffold_file):
            return {
                "valid": False,
                "errors": [f"skaffold.yaml not found in {manifests_path}"]
            }
        
        try:
            command = [self.skaffold_path, "config", "set", "--global", "collect-metrics", "false"]
            subprocess.run(command, capture_output=True, text=True, timeout=30)
            
            command = [self.skaffold_path, "diagnose", "--yaml-only"]
            result = subprocess.run(
                command,
                cwd=manifests_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                return {"valid": True, "output": result.stdout}
            else:
                return {
                    "valid": False,
                    "errors": [result.stderr or "Unknown validation error"]
                }
                
        except subprocess.TimeoutExpired:
            return {"valid": False, "errors": ["Skaffold config validation timed out"]}
        except Exception as e:
            return {"valid": False, "errors": [str(e)]}
    
    def _run_skaffold_dry_run(self, manifests_path: str) -> Dict[str, Any]:
        """Run Skaffold render to validate manifest generation."""
        try:
            command = [
                self.skaffold_path, 
                "render",
                "--digest-source=none",
                "--offline=true"
            ]
            
            result = subprocess.run(
                command,
                cwd=manifests_path,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            return {
                "success": result.returncode == 0,
                "rendered_manifests": result.stdout if result.returncode == 0 else None,
                "errors": result.stderr if result.returncode != 0 else None,
                "command": " ".join(command)
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "errors": f"Skaffold render timed out after {self.timeout} seconds"
            }
        except Exception as e:
            return {"success": False, "errors": str(e)}
    
    def _run_skaffold_deploy(self, manifests_path: str) -> Dict[str, Any]:
        """Deploy using Skaffold to a test namespace."""
        start_time =  time.time()
        test_namespace = f"test-{int(start_time)}"
        
        try:
            # Create test namespace
            subprocess.run([
                "kubectl", "create", "namespace", test_namespace
            ], capture_output=True, text=True, timeout=180)
            
            command = [
                self.skaffold_path,
                "run",
                "--namespace", test_namespace,
                "-f", "skaffold.yaml",
                
            ]
            
            result = subprocess.run(
                command,
                cwd=manifests_path,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            return {
                "success": result.returncode == 0,
                "namespace": test_namespace,
                "output": result.stdout,
                "errors": result.stderr if result.returncode != 0 else None,
                "deployment_time": time.strftime("%H:%M:%S", time.gmtime(time.time() - start_time))
            }
            
        except Exception as e:
            return {
                "success": False,
                "namespace": test_namespace,
                "errors": str(e)
            }
    
    def _check_service_health(self, manifests_path: str) -> Dict[str, Any]:
        """Check health of deployed services."""
        # This would check pod status, service endpoints, etc.
        # Implementation depends on your specific health check requirements
        return {
            "pods_ready": True,  # Placeholder
            "services_accessible": True,  # Placeholder
            "health_check_time": time.time()
        }
    
    def _cleanup_deployment(self, manifests_path: str):
        """Clean up test deployment."""
        try:
            subprocess.run([
                self.skaffold_path, "delete"
            ], cwd=manifests_path, capture_output=True, timeout=60)
        except Exception as e:
            self.logger.warning(f"Failed to cleanup deployment: {e}")
    
    def _determine_overall_status(self, results: Dict[str, Any]) -> str:
        """Determine overall validation status."""
        if results.get("errors"):
            return "failed"
        
        if not results.get("config_validation", {}).get("valid", False):
            return "failed"
        
        if not results.get("dry_run_results", {}).get("success", False):
            return "failed"
        
        deployment_results = results.get("deployment_results")
        if deployment_results and not deployment_results.get("success", False):
            return "failed"
        
        return "passed"