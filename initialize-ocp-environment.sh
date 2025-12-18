#!/usr/bin/env python3

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

# Static configuration
OPERATORS = [
    "advanced-cluster-management",
    "advanced-cluster-management-operator",
    "openshift-ai",
    "openshift-ai-operator",
    "openshift-virtualization",
    "openshift-virtualization-operator"
]

REPOSITORIES = [
    "rhacm-2.15-for-rhel-9-x86_64-rpms",
    "rhocp-4.20-for-rhel-9-x86_64-rpms"
]

PACKAGES = [
    "flightctl",
    "container-tools",
    "openshift-clients"
]

BUILD_DIR = "windguard-demo-build/microshift-build/"
IMAGE_BASE = "windguard-microshift"
IMAGE_TAG = "demo"
QCOW2_TAG = "demo-qcow2"
BOOTC_BUILDER = "registry.redhat.io/rhel9/bootc-image-builder:latest"
MICROSHIFT_KUBECONFIG = "/var/lib/microshift/resources/kubeadmin/kubeconfig"

def log(message, color=Colors.GREEN):
    print(f"{color}{message}{Colors.NC}")

def execute_step(step_name, command, shell=True, env=None):
    """Execute a command with logging"""
    log(f"\n[STEP] {step_name}", Colors.GREEN)
    try:
        if isinstance(command, list):
            result = subprocess.run(command, check=True, capture_output=False, env=env)
        else:
            result = subprocess.run(command, shell=shell, check=True, env=env)
        log(f"[SUCCESS] {step_name}", Colors.GREEN)
        return True
    except subprocess.CalledProcessError as e:
        log(f"[FAILED] {step_name}", Colors.RED)
        log(f"Error: {e}", Colors.RED)
        sys.exit(1)

def get_command_output(command, shell=True):
    """Execute command and return output"""
    result = subprocess.run(command, shell=shell, capture_output=True, text=True, check=True)
    return result.stdout.strip()

def main():
    # Load configuration
    config_file = sys.argv[1] if len(sys.argv) > 1 else "demo-config.yaml"

    if not Path(config_file).exists():
        log(f"Error: Configuration file '{config_file}' not found", Colors.RED)
        sys.exit(1)

    log(f"Loading configuration from {config_file}", Colors.BLUE)

    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    # Extract dynamic configuration
    redhat_reg = config['redhat_registry']
    private_reg = config['private_registry']
    ocp = config['ocp_cluster']

    # Build URLs from domain
    ocp_api_url = f"https://api.{ocp['domain']}:6443"

    # Setup environment variables
    env = os.environ.copy()
    env['OCP_CLUSTER_DOMAIN'] = ocp['domain']
    env['REGISTRY_URL'] = private_reg['url']
    env['REGISTRY_USER'] = private_reg['username']
    env['BOOTC_IMAGE'] = f"{private_reg['url']}/{private_reg['username']}/{IMAGE_BASE}:{IMAGE_TAG}"
    env['QCOW_IMAGE'] = f"{private_reg['url']}/{private_reg['username']}/{IMAGE_BASE}:{QCOW2_TAG}"

    log("=== MicroShift Device Image Build ===", Colors.GREEN)
    log(f"OCP Domain: {env['OCP_CLUSTER_DOMAIN']}", Colors.YELLOW)
    log(f"Private Registry: {env['REGISTRY_URL']}/{env['REGISTRY_USER']}", Colors.YELLOW)
    log(f"Boot Image: {env['BOOTC_IMAGE']}", Colors.YELLOW)

    # 2. Enable repositories
    repo_args = ' '.join([f"--enable {repo}" for repo in REPOSITORIES])
    execute_step(
        "Enabling repositories",
        f"subscription-manager repos {repo_args}",
        env=env
    )

    # 3. Install packages
    package_list = ' '.join(PACKAGES)
    execute_step(
        "Installing packages",
        f"dnf install -y {package_list}",
        env=env
    )

    # 4. Change to build directory
    build_dir = Path(BUILD_DIR)
    if not build_dir.exists():
        log(f"Error: Build directory '{build_dir}' not found", Colors.RED)
        sys.exit(1)

    os.chdir(build_dir)
    log(f"Changed to directory: {build_dir.absolute()}", Colors.BLUE)

    # 5. Login to registries
    execute_step(
        "Logging into private registry",
        f"podman login {private_reg['url']} --username {private_reg['username']} --password {private_reg['password']} --authfile=auth.json",
        env=env
    )

    execute_step(
        "Logging into registry.redhat.io",
        f"podman login registry.redhat.io --username {redhat_reg['username']} --password {redhat_reg['password']} --authfile=auth.json",
        env=env
    )

    # 6. Login to OpenShift
    execute_step(
        "Logging into OpenShift",
        f"oc login -u {ocp['username']} -p {ocp['password']} {ocp_api_url} --insecure-skip-tls-verify=true",
        env=env
    )

    # 7. Extract pull secret
    execute_step(
        "Extracting pull secret",
        f"oc get secret/pull-secret -n openshift-config --template='{{{{index .data \".dockerconfigjson\" | base64decode}}}}' > pull-secret",
        env=env
    )

    # 8. Get FlightCtl API server URL and login
    rhem_api_url = get_command_output(
        "oc get route -n open-cluster-management flightctl-api-route -o json | jq -r .spec.host"
    )
    env['RHEM_API_SERVER_URL'] = rhem_api_url

    execute_step(
        "Logging into FlightCtl",
        f"flightctl login --username={ocp['username']} --password={ocp['password']} https://{rhem_api_url} --insecure-skip-tls-verify",
        env=env
    )

    # 9. Verify FlightCtl version
    execute_step(
        "Checking FlightCtl version",
        "flightctl version",
        env=env
    )

    # 10. Request certificate
    execute_step(
        "Requesting FlightCtl certificate",
        f"flightctl certificate request --signer=enrollment --expiration=365d --output=embedded > config.yaml",
        env=env
    )

    # 11. Apply fleet configuration
    execute_step(
        "Applying fleet configuration",
        f"sed 's|BOOTC_IMAGE|{env['BOOTC_IMAGE']}|g' rhem-fleet.yml | flightctl apply -f -",
        env=env
    )

    # 12. Build bootc image
    execute_step(
        "Building bootc container image",
        f"podman build --rm --no-cache --build-arg OCP_CLUSTER_DOMAIN={env['OCP_CLUSTER_DOMAIN']} -t {env['BOOTC_IMAGE']} .",
        env=env
    )

    execute_step(
        "Pushing bootc image",
        f"podman push {env['BOOTC_IMAGE']}",
        env=env
    )

    # 13. Build QCOW2 image
    output_path = Path("output").absolute()
    execute_step(
        "Building QCOW2 image with bootc-image-builder",
        f"""podman run --rm -it --privileged --pull=newer \
            --security-opt label=type:unconfined_t \
            -v "{output_path}":/output \
            -v /var/lib/containers/storage:/var/lib/containers/storage \
            {BOOTC_BUILDER} \
            --type qcow2 \
            {env['BOOTC_IMAGE']}""",
        env=env
    )

    # 14. Build and push QCOW2 container
    execute_step(
        "Building QCOW2 container image",
        f"podman build --rm --no-cache -t {env['QCOW_IMAGE']} -f Containerfile.ocpvirt .",
        env=env
    )

    execute_step(
        "Pushing QCOW2 container image",
        f"podman push {env['QCOW_IMAGE']}",
        env=env
    )

# NUMBER 15 Must happen in another directory that is called windguard-demo-deploy

    # 15. Deploy to OpenShift Virtualization
    execute_step(
        "Creating namespace and services",
        f"oc apply -f windguard-namespace.yml -f windguard-vm-service.yml -f windguard-vm-routes.yml",
        env=env
    )

    execute_step(
        "Deploying VM to OpenShift Virtualization",
        f"sed 's|QCOW_IMAGE|{env['QCOW_IMAGE']}|g' windguard-vm-ocpvirt.yml | oc apply -f -",
        env=env
    )

    log("\n=== Build Complete ===", Colors.GREEN)
    log(f"Bootc Image: {env['BOOTC_IMAGE']}", Colors.YELLOW)
    log(f"QCOW2 Image: {env['QCOW_IMAGE']}", Colors.YELLOW)

if __name__ == "__main__":
    main()
