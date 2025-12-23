#!/usr/bin/env bash
#
# deploy-and-wait.sh
# -----------------------------------------
# 1. Applies manifests to the cluster
# 2. Waits until specified Argo CD Applications are Synced and Healthy
# 3. Patches the OpenShift Console to include the "flightctl-plugin"
#
# Requires: oc CLI (logged in)
# Default Argo CD namespace: openshift-gitops
#

# ======== CONFIGURATION ========
NAMESPACE="openshift-gitops"   # Namespace where Argo CD applications reside
INTERVAL=10                    # Seconds between checks
TIMEOUT=600                    # Timeout per application in seconds
CONSOLE_RESOURCE="console.operator.openshift.io/cluster"
# ===============================

# ======== COLORS ========
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
# =========================

# ---- Helper: timestamped log ----
log() { echo -e "[$(date +'%H:%M:%S')] $*"; }

# ---- Handle Ctrl+C gracefully ----
trap 'log "${YELLOW}🛑 Interrupted by user.${NC}"; exit 130' INT

# ---- Helper: usage message ----
usage() {
  echo "Usage: $0 <app1> [app2 ...]"
  echo
  echo "Example:"
  echo "  $0 backend frontend database"
  echo
  echo "Environment variables:"
  echo "  NAMESPACE   (default: openshift-gitops)"
  echo "  INTERVAL    (default: 10)"
  echo "  TIMEOUT     (default: 600)"
  exit 1
}

# ---- Check arguments ----
if [ $# -lt 1 ]; then
  usage
fi

# ---- Apply manifests section ----
log "${BLUE}🚀 Applying manifests to the cluster...${NC}"
# ===========================================================
# 🧱 BOILERPLATE SECTION — add your manifests below
# Example:
# oc apply -f ./manifests/namespace.yaml
# oc apply -f ./manifests/configmap.yaml
# oc apply -k ./kustomize/overlays/prod
# ===========================================================
log "(No manifests applied yet — add your oc apply commands above)"
echo

# ---- Function to get ArgoCD app status ----
get_status() {
  local app="$1"
  local sync health
  sync=$(oc get applications.argoproj.io "$app" -n "$NAMESPACE" -o jsonpath='{.status.sync.status}' 2>/dev/null)
  health=$(oc get applications.argoproj.io "$app" -n "$NAMESPACE" -o jsonpath='{.status.health.status}' 2>/dev/null)
  echo "$sync" "$health"
}

# ---- Function to wait for ArgoCD Application ----
wait_for_app() {
  local app="$1"
  local start elapsed sync health
  start=$(date +%s)

  log "${BLUE}🔍 Checking ArgoCD Application:${NC} $app"

  while true; do
    read -r sync health <<<"$(get_status "$app")"

    if [ -z "$sync" ]; then
      log "${RED}❌ Application '$app' not found in namespace '$NAMESPACE'.${NC}"
      return 2
    fi

    if [[ "$sync" == "Synced" && "$health" == "Healthy" ]]; then
      log "${GREEN}✅ $app is Synced and Healthy.${NC}"
      return 0
    fi

    log "${YELLOW}⏳ $app -> Sync=$sync, Health=$health (waiting...)${NC}"
    sleep "$INTERVAL"

    elapsed=$(( $(date +%s) - start ))
    if (( elapsed >= TIMEOUT )); then
      log "${RED}❌ Timeout reached for $app after ${TIMEOUT}s.${NC}"
      return 1
    fi
  done
}

# ---- Wait for all specified ArgoCD apps ----
for app in "$@"; do
  wait_for_app "$app" || exit $?
done

log "${GREEN}🎉 All specified applications are Synced and Healthy.${NC}"
echo

# ---- Patch the OpenShift Console to add flightctl-plugin ----
log "${BLUE}🧩 Patching OpenShift Console to include 'flightctl-plugin'...${NC}"

# Check if plugin is already present
if oc get "$CONSOLE_RESOURCE" -o jsonpath='{.spec.plugins}' | grep -q '"flightctl-plugin"'; then
  log "${GREEN}✅ 'flightctl-plugin' already present in spec.plugins${NC}"
else
  # Use safer merge patch to handle cases with missing .spec.plugins
  oc patch "$CONSOLE_RESOURCE" --type=merge -p '{"spec": {"plugins": ["flightctl-plugin"]}}'
  if [ $? -eq 0 ]; then
    log "${GREEN}✅ Successfully added 'flightctl-plugin' to Console spec.plugins${NC}"
  else
    log "${RED}❌ Failed to patch the Console resource.${NC}"
    exit 3
  fi
fi

log "${GREEN}🏁 Deployment complete — all systems operational.${NC}"
