#!/usr/bin/env python3
"""
deploy-edge-fleet.py
Deploy FlightCtl fleet configuration and OpenShift Virtualization VMs
"""

import yaml
import subprocess
import sys
import os
from pathlib import Path

class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

# Constants
IMAGE_BASE = "windguard-microshift"
IMAGE_TAG = "demo"
QCOW2_TAG = "demo-qcow2"

def log(message, color=Colors.GREEN):
    """Print colored log message"""
    print(f"{color}{message}{Colors.NC}")

def execute_step(step_name, command, shell=True, env=None):
    """Execute a command with logging and error handling"""
    log(f"\n[STEP] {step_name}", Colors.BLUE)
    try:
        if isinstance(command, list):
            subprocess.run(command, check=True, capture_output=False, env=env)
        else:
            subprocess.run(command, shell=shell, check=True, env=env)
        log(f"[SUCCESS] {step_name}", Colors.GREEN)
        return True
    except subprocess.CalledProcessError as e:
        log(f"[FAILED] {step_name}", Colors.RED)
        log(f"Error: {e}", Colors.RED)
        sys.exit(1)

def get_command_output(command, shell=True):
    """Execute command and return output"""
    try:
        result = subprocess.run(
            command,
            shell=shell,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        log(f"Error executing command: {e}", Colors.RED)
        sys.exit(1)

def load_config(config_file):
    """Load and validate configuration file"""
    if not Path(config_file).exists():
        log(f"Error: Configuration file '{config_file}' not found", Colors.RED)
        sys.exit(1)

    log(f"Loading configuration from {config_file}", Colors.BLUE)

    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    # Validate required fields
    required_keys = ['private_registry', 'ocp_cluster']
    for key in required_keys:
        if key not in config:
            log(f"Error: Missing required key '{key}' in config file", Colors.RED)
            sys.exit(1)

    return config

def setup_environment(config):
    """Setup environment variables from config"""
    private_reg = config['private_registry']
    ocp = config['ocp_cluster']

    ocp_api_url = f"https://api.{ocp['domain']}:6443"

    env = os.environ.copy()
    env['OCP_CLUSTER_DOMAIN'] = ocp['domain']
    env['REGISTRY_URL'] = private_reg['url']
    env['REGISTRY_USER'] = private_reg['username']
    env['BOOTC_IMAGE'] = f"{private_reg['url']}/{private_reg['username']}/{IMAGE_BASE}:{IMAGE_TAG}"
    env['QCOW_IMAGE'] = f"{private_reg['url']}/{private_reg['username']}/{IMAGE_BASE}:{QCOW2_TAG}"

    return env, private_reg, ocp, ocp_api_url

def verify_prerequisites():
    """Verify required files and configurations exist"""
    required_files = [
        "demo-environment-setup/rhem-windguard-repo.yml",
        "demo-environment-setup/rhem-windguard-fleet.yml",
        "demo-environment-setup/ocpvirt-windguard-namespace.yml",
        "demo-environment-setup/ocpvirt-windguard-vm-service.yml",
        "demo-environment-setup/ocpvirt-windguard-vm-routes.yml",
        "demo-environment-setup/ocpvirt-windguard-vm-ocpvirt.yml"
    ]

    missing_files = [f for f in required_files if not Path(f).exists()]

    if missing_files:
        log("Error: Missing required manifest files:", Colors.RED)
        for f in missing_files:
            log(f"  - {f}", Colors.RED)
        sys.exit(1)

def main():
    """Main execution function"""
    # Parse arguments
    config_file = sys.argv[1] if len(sys.argv) > 1 else "demo-config.yaml"

    # Load configuration
    config = load_config(config_file)
    env, private_reg, ocp, ocp_api_url = setup_environment(config)

    # Verify prerequisites
    verify_prerequisites()

    # Display configuration
    log("\n=== WindGuard Fleet Deployment ===", Colors.GREEN)
    log(f"OCP Domain: {env['OCP_CLUSTER_DOMAIN']}", Colors.YELLOW)
    log(f"Bootc Image: {env['BOOTC_IMAGE']}", Colors.YELLOW)
    log(f"QCOW2 Image: {env['QCOW_IMAGE']}", Colors.YELLOW)

    # Login to OpenShift
    log("\n=== OpenShift Authentication ===", Colors.GREEN)
    execute_step(
        "Logging into OpenShift cluster",
        f"oc login -u {ocp['username']} -p {ocp['password']} {ocp_api_url} --insecure-skip-tls-verify=true",
        env=env
    )

    # Get FlightCtl API URL and login
    log("\n=== FlightCtl Authentication ===", Colors.GREEN)
    rhem_api_url = get_command_output(
        "oc get route -n open-cluster-management flightctl-api-route -o json | jq -r .spec.host"
    )
    env['RHEM_API_SERVER_URL'] = rhem_api_url
    log(f"FlightCtl API: {rhem_api_url}", Colors.YELLOW)

    execute_step(
        "Logging into FlightCtl",
        f"flightctl login --username={ocp['username']} --password={ocp['password']} https://{rhem_api_url} --insecure-skip-tls-verify",
        env=env
    )

    # Deploy FlightCtl Repository
    log("\n=== Deploying FlightCtl Repository ===", Colors.GREEN)
    execute_step(
        "Applying FlightCtl repository configuration",
        "flightctl apply -f demo-environment-setup/rhem-windguard-repo.yml",
        env=env
    )

    # Deploy FlightCtl Fleet
    log("\n=== Deploying FlightCtl Fleet ===", Colors.GREEN)
    execute_step(
        "Applying FlightCtl fleet configuration",
        f"sed 's|BOOTC_IMAGE|{env['BOOTC_IMAGE']}|g' demo-environment-setup/rhem-windguard-fleet.yml | flightctl apply -f -",
        env=env
    )

    # Create OpenShift Virtualization namespace and services
    log("\n=== Deploying OpenShift Virtualization Resources ===", Colors.GREEN)
    execute_step(
        "Creating namespace and services",
        "oc apply -f demo-environment-setup/ocpvirt-windguard-namespace.yml "
        "-f demo-environment-setup/ocpvirt-windguard-vm-service.yml "
        "-f demo-environment-setup/ocpvirt-windguard-vm-routes.yml",
        env=env
    )

    # Deploy Virtual Machine
    execute_step(
        "Deploying Virtual Machine to OpenShift Virtualization",
        f"sed 's|QCOW_IMAGE|{env['QCOW_IMAGE']}|g' demo-environment-setup/ocpvirt-windguard-vm-ocpvirt.yml | oc apply -f -",
        env=env
    )

    # Summary
    log("\n=== Deployment Complete ===", Colors.GREEN)
    log("FlightCtl repository and fleet have been configured", Colors.YELLOW)
    log("Virtual machines are being deployed to OpenShift Virtualization", Colors.YELLOW)

    log("\n=== Next Steps ===", Colors.BLUE)
    log("1. Check VM status: oc get vms -n windguard-demo", Colors.YELLOW)
    log("2. List enrolled devices: flightctl get devices", Colors.YELLOW)
    log("3. Access FlightCtl console through OpenShift web console", Colors.YELLOW)

if __name__ == "__main__":
    main()
