#!/usr/bin/env python3
"""
build-edge-images.py
Build bootable container and QCOW2 images for WindGuard edge devices
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
REPOSITORIES = [
    "rhacm-2.15-for-rhel-9-x86_64-rpms",
    "rhocp-4.20-for-rhel-9-x86_64-rpms"
]

PACKAGES = [
    "flightctl",
    "container-tools",
    "openshift-clients"
]

IMAGE_BASE = "windguard-microshift"
IMAGE_TAG = "demo"
QCOW2_TAG = "demo-qcow2"
BOOTC_BUILDER = "registry.redhat.io/rhel9/bootc-image-builder:latest"
BUILD_DIR = "demo-environment-setup/microshift-im-build"

def log(message, color=Colors.GREEN):
    """Print colored log message"""
    print(f"{color}{message}{Colors.NC}")

def execute_step(step_name, command, shell=True, env=None, cwd=None):
    """Execute a command with logging and error handling"""
    log(f"\n[STEP] {step_name}", Colors.BLUE)
    try:
        if isinstance(command, list):
            subprocess.run(command, check=True, capture_output=False, env=env, cwd=cwd)
        else:
            subprocess.run(command, shell=shell, check=True, env=env, cwd=cwd)
        log(f"[SUCCESS] {step_name}", Colors.GREEN)
        return True
    except subprocess.CalledProcessError as e:
        log(f"[FAILED] {step_name}", Colors.RED)
        log(f"Error: {e}", Colors.RED)
        sys.exit(1)

def get_command_output(command, shell=True, cwd=None):
    """Execute command and return output"""
    try:
        result = subprocess.run(
            command,
            shell=shell,
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd
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
    required_keys = ['redhat_registry', 'private_registry', 'ocp_cluster']
    for key in required_keys:
        if key not in config:
            log(f"Error: Missing required key '{key}' in config file", Colors.RED)
            sys.exit(1)

    return config

def setup_environment(config):
    """Setup environment variables from config"""
    redhat_reg = config['redhat_registry']
    private_reg = config['private_registry']
    ocp = config['ocp_cluster']

    ocp_api_url = f"https://api.{ocp['domain']}:6443"

    env = os.environ.copy()
    env['OCP_CLUSTER_DOMAIN'] = ocp['domain']
    env['REGISTRY_URL'] = private_reg['url']
    env['REGISTRY_USER'] = private_reg['username']
    env['BOOTC_IMAGE'] = f"{private_reg['url']}/{private_reg['username']}/{IMAGE_BASE}:{IMAGE_TAG}"
    env['QCOW_IMAGE'] = f"{private_reg['url']}/{private_reg['username']}/{IMAGE_BASE}:{QCOW2_TAG}"

    return env, redhat_reg, private_reg, ocp, ocp_api_url

def main():
    """Main execution function"""
    # Parse arguments
    config_file = sys.argv[1] if len(sys.argv) > 1 else "demo-config.yaml"

    # Load configuration
    config = load_config(config_file)
    env, redhat_reg, private_reg, ocp, ocp_api_url = setup_environment(config)

    # Verify build directory exists
    build_path = Path(BUILD_DIR)
    if not build_path.exists():
        log(f"Error: Build directory '{BUILD_DIR}' not found", Colors.RED)
        sys.exit(1)

    # Display configuration
    log("\n=== WindGuard Edge Image Build ===", Colors.GREEN)
    log(f"Build Directory: {BUILD_DIR}", Colors.YELLOW)
    log(f"OCP Domain: {env['OCP_CLUSTER_DOMAIN']}", Colors.YELLOW)
    log(f"Private Registry: {env['REGISTRY_URL']}/{env['REGISTRY_USER']}", Colors.YELLOW)
    log(f"Bootc Image: {env['BOOTC_IMAGE']}", Colors.YELLOW)
    log(f"QCOW2 Image: {env['QCOW_IMAGE']}", Colors.YELLOW)

    # Enable repositories
    log("\n=== System Setup ===", Colors.GREEN)
    repo_args = ' '.join([f"--enable {repo}" for repo in REPOSITORIES])
    execute_step(
        "Enabling RHEL repositories",
        f"subscription-manager repos {repo_args}",
        env=env
    )

    # Install packages
    package_list = ' '.join(PACKAGES)
    execute_step(
        "Installing required packages",
        f"dnf install -y {package_list}",
        env=env
    )

    # Login to registries
    log("\n=== Registry Authentication ===", Colors.GREEN)
    execute_step(
        "Logging into private registry",
        f"podman login {private_reg['url']} --username {private_reg['username']} --password {private_reg['password']} --authfile=auth.json",
        env=env,
        cwd=BUILD_DIR
    )

    execute_step(
        "Logging into registry.redhat.io",
        f"podman login registry.redhat.io --username {redhat_reg['username']} --password {redhat_reg['password']} --authfile=auth.json",
        env=env,
        cwd=BUILD_DIR
    )

    # Login to OpenShift
    log("\n=== OpenShift Setup ===", Colors.GREEN)
    execute_step(
        "Logging into OpenShift cluster",
        f"oc login -u {ocp['username']} -p {ocp['password']} {ocp_api_url} --insecure-skip-tls-verify=true",
        env=env
    )

    # Extract pull secret
    execute_step(
        "Extracting OpenShift pull secret",
        "oc get secret/pull-secret -n openshift-config --template='{{index .data \".dockerconfigjson\" | base64decode}}' > pull-secret",
        env=env,
        cwd=BUILD_DIR
    )

    # Get FlightCtl API URL and login
    log("\n=== FlightCtl Setup ===", Colors.GREEN)
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

    execute_step(
        "Verifying FlightCtl version",
        "flightctl version",
        env=env
    )

    # Request enrollment certificate
    execute_step(
        "Requesting FlightCtl enrollment certificate",
        "flightctl certificate request --signer=enrollment --expiration=365d --output=embedded > config.yaml",
        env=env,
        cwd=BUILD_DIR
    )

    # Build bootc image
    log("\n=== Building Bootable Container Image ===", Colors.GREEN)
    execute_step(
        "Building bootc container image",
        f"podman build --rm --no-cache -t {env['BOOTC_IMAGE']} .",
        env=env,
        cwd=BUILD_DIR
    )

    execute_step(
        "Pushing bootc image to registry",
        f"podman push {env['BOOTC_IMAGE']} --authfile=auth.json",
        env=env
    )

    # Build QCOW2 image
    log("\n=== Building QCOW2 Disk Image ===", Colors.GREEN)
    output_path = (build_path / "output").absolute()
    output_path.mkdir(exist_ok=True)

    execute_step(
        "Building QCOW2 image with bootc-image-builder",
        f"podman run --rm -it --privileged --pull=newer "
        f"--security-opt label=type:unconfined_t "
        f"-v {output_path}:/output "
        f"-v ./config.toml:/config.toml "
        f"-v /var/lib/containers/storage:/var/lib/containers/storage "
        f"{BOOTC_BUILDER} --type qcow2 {env['BOOTC_IMAGE']}",
        env=env,
        cwd=BUILD_DIR
    )

    # Build and push QCOW2 container
    log("\n=== Creating QCOW2 Container Image ===", Colors.GREEN)
    execute_step(
        "Building QCOW2 container image",
        f"podman build --rm --no-cache -t {env['QCOW_IMAGE']} -f Containerfile.ocpvirt .",
        env=env,
        cwd=BUILD_DIR
    )

    execute_step(
        "Pushing QCOW2 container image to registry",
        f"podman push {env['QCOW_IMAGE']} --authfile=auth.json",
        env=env
    )

    # Summary
    log("\n=== Build Complete ===", Colors.GREEN)
    log(f"Bootc Image: {env['BOOTC_IMAGE']}", Colors.YELLOW)
    log(f"QCOW2 Image: {env['QCOW_IMAGE']}", Colors.YELLOW)
    log("\nRun 'deploy-edge-fleet.py' to deploy the edge devices", Colors.BLUE)

if __name__ == "__main__":
    main()
