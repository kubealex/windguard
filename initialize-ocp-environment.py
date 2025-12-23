#!/usr/bin/env python3
"""
deploy-and-wait.py
-----------------------------------------
1. Applies manifests to the cluster
2. Waits until specified Argo CD Applications are Synced and Healthy
3. Patches the OpenShift Console to include the "flightctl-plugin"

Requires: oc CLI (logged in) or demo-config.yaml for authentication
"""

import argparse
import sys
import time
import subprocess
import json
import signal
from datetime import datetime
from pathlib import Path
import yaml

# ======== CONFIGURATION ========
DEFAULT_NAMESPACE = "openshift-gitops"
DEFAULT_INTERVAL = 10
DEFAULT_TIMEOUT = 600
CONSOLE_RESOURCE = "console.operator.openshift.io/cluster"
CONFIG_FILE = "demo-config.yaml"
# ===============================

# ======== COLORS ========
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'
# =========================


class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'


def log(message, color=None):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    if color:
        print(f"{color}[{timestamp}] {message}{Colors.NC}")
    else:
        print(f"[{timestamp}] {message}")


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    log("🛑 Interrupted by user.", Colors.YELLOW)
    sys.exit(130)


def load_config(config_path):
    """Load configuration from YAML file"""
    if not Path(config_path).exists():
        return None

    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        log(f"⚠️  Warning: Could not load config file: {e}", Colors.YELLOW)
        return None


def login_to_cluster(config):
    """Login to OpenShift cluster using config"""
    if not config:
        log("No config file found, assuming already logged in", Colors.YELLOW)
        return True

    try:
        server = config.get('server')
        token = config.get('token')

        if not server or not token:
            log("Config missing 'server' or 'token', skipping login", Colors.YELLOW)
            return True

        log(f"🔐 Logging into cluster: {server}", Colors.BLUE)

        cmd = ['oc', 'login', server, '--token', token, '--insecure-skip-tls-verify=true']
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            log("✅ Successfully logged into cluster", Colors.GREEN)
            return True
        else:
            log(f"❌ Login failed: {result.stderr}", Colors.RED)
            return False

    except Exception as e:
        log(f"❌ Error during login: {e}", Colors.RED)
        return False


def run_oc_command(cmd):
    """Execute oc command and return output"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return 1, "", str(e)


def apply_manifests():
    """Apply manifests to the cluster"""
    log("🚀 Applying manifests to the cluster...", Colors.BLUE)
    log("(No manifests applied yet — add your oc apply commands here)")
    # ===========================================================
    # 🧱 BOILERPLATE SECTION — add your manifests below
    # Example:
    # run_oc_command(['oc', 'apply', '-f', './manifests/namespace.yaml'])
    # run_oc_command(['oc', 'apply', '-f', './manifests/configmap.yaml'])
    # run_oc_command(['oc', 'apply', '-k', './kustomize/overlays/prod'])
    # ===========================================================
    print()


def get_app_status(app_name, namespace):
    """Get ArgoCD application sync and health status"""
    sync_cmd = [
        'oc', 'get', 'applications.argoproj.io', app_name,
        '-n', namespace,
        '-o', 'jsonpath={.status.sync.status}'
    ]
    health_cmd = [
        'oc', 'get', 'applications.argoproj.io', app_name,
        '-n', namespace,
        '-o', 'jsonpath={.status.health.status}'
    ]

    sync_code, sync_status, _ = run_oc_command(sync_cmd)
    health_code, health_status, _ = run_oc_command(health_cmd)

    if sync_code != 0 or health_code != 0:
        return None, None

    return sync_status, health_status


def wait_for_app(app_name, namespace, interval, timeout):
    """Wait for ArgoCD Application to be Synced and Healthy"""
    log(f"🔍 Checking ArgoCD Application: {app_name}", Colors.BLUE)

    start_time = time.time()

    while True:
        sync_status, health_status = get_app_status(app_name, namespace)

        if sync_status is None:
            log(f"❌ Application '{app_name}' not found in namespace '{namespace}'.", Colors.RED)
            return False

        if sync_status == "Synced" and health_status == "Healthy":
            log(f"✅ {app_name} is Synced and Healthy.", Colors.GREEN)
            return True

        log(f"⏳ {app_name} -> Sync={sync_status}, Health={health_status} (waiting...)", Colors.YELLOW)
        time.sleep(interval)

        elapsed = time.time() - start_time
        if elapsed >= timeout:
            log(f"❌ Timeout reached for {app_name} after {timeout}s.", Colors.RED)
            return False


def patch_console():
    """Patch OpenShift Console to add flightctl-plugin"""
    log("🧩 Patching OpenShift Console to include 'flightctl-plugin'...", Colors.BLUE)

    # Check if plugin is already present
    check_cmd = [
        'oc', 'get', CONSOLE_RESOURCE,
        '-o', 'jsonpath={.spec.plugins}'
    ]
    code, output, _ = run_oc_command(check_cmd)

    if code == 0 and 'flightctl-plugin' in output:
        log("✅ 'flightctl-plugin' already present in spec.plugins", Colors.GREEN)
        return True

    # Patch the console
    patch_cmd = [
        'oc', 'patch', CONSOLE_RESOURCE,
        '--type=merge',
        '-p', '{"spec": {"plugins": ["flightctl-plugin"]}}'
    ]
    code, _, stderr = run_oc_command(patch_cmd)

    if code == 0:
        log("✅ Successfully added 'flightctl-plugin' to Console spec.plugins", Colors.GREEN)
        return True
    else:
        log(f"❌ Failed to patch the Console resource: {stderr}", Colors.RED)
        return False


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description='Deploy manifests and wait for ArgoCD Applications to be ready',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s backend frontend database
  %(prog)s --namespace my-gitops --timeout 900 app1 app2

Environment variables can also be used:
  NAMESPACE   (default: openshift-gitops)
  INTERVAL    (default: 10)
  TIMEOUT     (default: 600)
        """
    )

    parser.add_argument(
        'applications',
        nargs='+',
        help='ArgoCD application names to wait for'
    )
    parser.add_argument(
        '--namespace', '-n',
        default=DEFAULT_NAMESPACE,
        help=f'Namespace where Argo CD applications reside (default: {DEFAULT_NAMESPACE})'
    )
    parser.add_argument(
        '--interval', '-i',
        type=int,
        default=DEFAULT_INTERVAL,
        help=f'Seconds between checks (default: {DEFAULT_INTERVAL})'
    )
    parser.add_argument(
        '--timeout', '-t',
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f'Timeout per application in seconds (default: {DEFAULT_TIMEOUT})'
    )
    parser.add_argument(
        '--config', '-c',
        default=CONFIG_FILE,
        help=f'Path to config file (default: {CONFIG_FILE})'
    )
    parser.add_argument(
        '--skip-login',
        action='store_true',
        help='Skip cluster login (assume already logged in)'
    )

    args = parser.parse_args()

    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    # Login to cluster if config provided and not skipped
    if not args.skip_login:
        config = load_config(args.config)
        if not login_to_cluster(config):
            log("❌ Failed to login to cluster", Colors.RED)
            sys.exit(1)

    # Apply manifests
    apply_manifests()

    # Wait for all applications
    for app in args.applications:
        if not wait_for_app(app, args.namespace, args.interval, args.timeout):
            sys.exit(2)

    log("🎉 All specified applications are Synced and Healthy.", Colors.GREEN)
    print()

    # Patch console
    if not patch_console():
        sys.exit(3)

    log("🏁 Deployment complete — all systems operational.", Colors.GREEN)
    sys.exit(0)


if __name__ == '__main__':
    main()
