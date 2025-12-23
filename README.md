# WindGuard Demo

A comprehensive demonstration environment for **Red Hat Edge Manager (FlightCtl)** showcasing edge device fleet management, workload deployment, and GitOps automation on OpenShift.

## 🎯 Demo Purpose

WindGuard demonstrates a complete edge computing solution that combines:

- **Fleet Management**: Manage multiple edge devices using Red Hat Edge Manager (FlightCtl)
- **Edge Workloads**: Deploy containerized applications to edge devices running MicroShift
- **GitOps Automation**: Automated deployment and configuration management using OpenShift GitOps (ArgoCD)
- **Edge-to-Cloud Integration**: Seamless integration between edge devices and central OpenShift cluster

This demo showcases how organizations can efficiently manage thousands of edge devices from a centralized control plane, deploying workloads and updates at scale with full visibility and control.

## 📋 Architecture Overview

The demo environment consists of:

1. **OpenShift Cluster (Hub)**: Central management cluster running:
   - Red Hat Edge Manager (FlightCtl) for device fleet management
   - OpenShift GitOps (ArgoCD) for automated deployments
   - OpenShift Virtualization for simulating edge device as VMs
   - FlightCtl Console UI plugin for device visibility

2. **Edge Devices (Fleet)**: Virtual machines running:
   - MicroShift (lightweight Kubernetes for edge)
   - FlightCtl agent for enrollment and management
   - Containerized workloads deployed via GitOps

3. **Workload Applications**: Sample applications demonstrating edge computing use cases, including Windguard.

## 🔧 Prerequisites

### Required Software

- **RHEL 9 System**: For building bootable container images
- **OpenShift Cluster**: Version 4.12 or later with:
  - Advanced Cluster Management (ACM) 2.13+
  - OpenShift Virtualization
  - Sufficient resources for GitOps and Edge Manager operators
- **Podman**: Container runtime for building images
- **OpenShift CLI (`oc`)**: Installed and configured
- **Python 3.6+**: For running automation scripts

### Required Access

- Red Hat Customer Portal credentials (for package repositories)
- OpenShift cluster admin credentials
- Private container registry (Quay.io or similar)

## 🚀 Quick Start

### Step 1: Clone the Repository

```bash
git clone https://github.com/kubealex/windguard.git
cd windguard
```

### Step 2: Create Configuration File

Create a `demo-config.yaml` file with your credentials and cluster information:

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
  domain: "your-cluster.example.com"  # The cluster domain without .apps
  username: "your-cluster-username"
  password: "your-cluster-password"
```

**Security Note**: Add `demo-config.yaml` to `.gitignore`:
```bash
echo "demo-config.yaml" >> .gitignore
chmod 600 demo-config.yaml
```

### Step 3: Initialize OpenShift Environment

Run the initialization script to set up the base infrastructure:

```bash
python3 initialize-ocp-environment.py
```

**What it does:**
- Logs into your OpenShift cluster
- Installs required operators (ACM, GitOps, Virtualization)
- Enables Red Hat Edge Manager (FlightCtl) in ACM
- Configures namespaces and RBAC permissions
- Deploys ArgoCD applications for GitOps management
- Patches the OpenShift Console to include FlightCtl plugin

### Step 4: Build and Deploy Edge Images

#### Build

Run the setup script to build edge device images and deploy the fleet:

```bash
python3 build-microshift-image.py
```

**What it does:**
- Enables required RHEL repositories on the build system
- Installs FlightCtl CLI and container tools
- Authenticates to container registries
- Logs into FlightCtl service
- Generates enrollment certificates for edge devices
- Creates FlightCtl repository and fleet configurations
- Builds bootable container image with MicroShift and FlightCtl agent
- Creates QCOW2 disk image for virtualization
- Pushes images to your private registry
- Deploys virtual machines to OpenShift Virtualization
- Enrolls VMs as edge devices in FlightCtl

#### Deploy

Run the setup script to deploy the fleet:

```bash
python3 deploy-windguard-fleet.py
```
**What it does:**
- Deploys the RHEM Fleet configuration and Repositories for the manifests
- Deploys virtual machines to OpenShift Virtualization
- Enrolls VMs as edge devices in FlightCtl

### Step 5: Verify the Installation

Check that all components are running:

```bash
# Check ArgoCD applications
oc get applications -n openshift-gitops

# Check FlightCtl service
oc get pods -n open-cluster-management | grep flightctl

# Check virtual machines
oc get vms -n windguard-demo

# List enrolled devices
flightctl get devices
```

## 🎮 Using the Demo

### Access the FlightCtl Console

1. Navigate to **OpenShift Console**
2. Look for **Fleet Management** in the left navigation menu
3. View enrolled devices, their status, and configuration
4. Monitor device health and workload deployments

### Deploying Workloads

Workloads are managed via GitOps in the `windguard-workload` directory. The ArgoCD application automatically syncs changes from the repository to edge devices.

## 📂 Repository Structure

```
windguard/
├── demo-environment-setup/           # Manifests and configurations
│   ├── rhem-windguard-fleet.yml     # FlightCtl fleet definition
│   ├── rhem-windguard-repo.yml      # FlightCtl repository config
│   ├── ocpvirt-windguard-*.yml      # OpenShift Virtualization configs
│   └── ...
├── windguard-fleet/                  # Edge device configurations
│   └── etc/microshift/               # MicroShift configurations
├── windguard-workload/               # Edge workload applications
├── initialize-ocp-environment.py     # OpenShift environment setup
├── setup-ocp-environment.py          # Edge image build and deployment
├── deploy-and-wait.py                # Utility for waiting on ArgoCD apps
├── Containerfile                     # Bootable container image definition
├── Containerfile.ocpvirt             # QCOW2 image wrapper
└── demo-config.yaml                  # Your configuration (not in repo)
```
## 🧹 Cleanup

To remove the demo environment:

```bash
# Remove VMs and workloads
oc delete project windguard-demo

# Remove FlightCtl fleet and devices
flightctl delete fleet windguard-fleet
flightctl delete devices --all

# Remove ArgoCD applications
oc delete application --all -n openshift-gitops

# Remove operators (optional)
oc delete subscription openshift-gitops-operator -n openshift-operators
```

## 📚 Additional Resources

- [Red Hat Edge Manager Documentation](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/2.13/html/edge_manager/)
- [FlightCtl Project](https://github.com/flightctl/flightctl)
- [OpenShift GitOps Documentation](https://docs.openshift.com/gitops/latest/)
- [MicroShift Documentation](https://docs.redhat.com/en/documentation/red_hat_build_of_microshift/)
- [OpenShift Virtualization](https://docs.openshift.com/container-platform/latest/virt/about_virt/about-virt.html)

## 👤 Authors

- **Alessandro Rossi** ([@kubealex](https://github.com/kubealex))
- **Luca Ferrari** ([@lucamaf](https://github.com/lucamaf))

## 📝 License

This demo is provided as-is for educational and demonstration purposes.

---

**Note**: Red Hat Edge Manager is a Technology Preview feature. Technology Preview features are not supported with Red Hat production service level agreements (SLAs) and might not be functionally complete.
