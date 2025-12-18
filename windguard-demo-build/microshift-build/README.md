# MicroShift Device Image Build Automation

Configuration-driven automation for building MicroShift device images with FlightCtl integration and OpenShift Virtualization deployment.

## Prerequisites

- RHEL 9 system with subscription-manager access
- Access to OpenShift cluster
- Podman installed
- Python 3.9+ (for Python script) or Bash 4+ (for shell script)
- PyYAML library (for Python script): `pip install pyyaml`

## Configuration

Only **dynamic values** need to be configured in `config.yaml`:

```yaml
# Red Hat Registry Configuration
redhat_registry:
  username: "your-redhat-username"
  password: "your-redhat-password"

# Private Registry Configuration (Quay.io or custom)
private_registry:
  url: "quay.io"  # Change if using different registry
  username: "your-registry-user"
  password: "your-registry-password"

# OpenShift Cluster Configuration
ocp_cluster:
  domain: "cluster-k7jhl.dynamic.redhatworkshops.io" # The domain of the cluster, without the *.apps
  username: "your-cluster-admin-user"
  password: "your-cluster-password"
```

### What's NOT in the config

The following are **hardcoded** in the scripts as they rarely change:

- **Operators**: ACM, OpenShift AI, OpenShift Virtualization
- **Repositories**: RHACM and RHOCP repos for RHEL 9
- **Packages**: flightctl, container-tools, openshift-clients
- **Image names**: windguard-microshift (base), demodot/demodot-qcow2 (tags)
- **File paths**: windguard-demo-build/microshift-build/, standard k8s manifests
- **URLs derived from domain**: `api.{domain}:6443`, `*.apps.{domain}`

## Usage

### Python Script (Recommended)

```bash
# Install dependencies
pip install pyyaml

# Make executable
chmod +x build-microshift.py

# Run with default config.yaml
./build-microshift.py

# Run with custom config
./build-microshift.py my-config.yaml
```

## Build Process

The automation performs these steps in order:

1. **Repository Configuration** - Enables RHACM and RHOCP repositories
2. **Package Installation** - Installs FlightCtl, container tools, and OCP clients
3. **Registry Authentication** - Logs into private registry and registry.redhat.io
4. **OpenShift Login** - Authenticates to `https://api.{domain}:6443`
5. **Pull Secret Extraction** - Retrieves cluster pull secret
6. **FlightCtl Setup** - Configures FlightCtl API connection and certificates
7. **Fleet Configuration** - Applies FlightCtl fleet template
8. **Bootc Image Build** - Builds and pushes bootc container image
9. **QCOW2 Generation** - Creates QCOW2 disk image using bootc-image-builder
10. **QCOW2 Container** - Packages QCOW2 for OpenShift Virtualization
11. **VM Deployment** - Deploys VM to OpenShift Virtualization

## Output

Successful build produces:

- **Bootc container image**: `{private_registry.url}/{private_registry.username}/windguard-microshift:demodot`
- **QCOW2 disk image**: `./windguard-demo-build/microshift-build/output/qcow2/disk.qcow2`
- **QCOW2 container image**: `{private_registry.url}/{private_registry.username}/windguard-microshift:demodot-qcow2`
- **Running VM** in OpenShift Virtualization

## Security Notes

⚠️ **Important:** The `config.yaml` file contains credentials.

**Best Practices:**
- Do not commit credentials to version control
- Restrict file permissions: `chmod 600 config.yaml`
- Use `.gitignore` to exclude config.yaml
- Consider using environment variables for CI/CD
