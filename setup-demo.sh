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
echo "🚀 Applying manifests to the cluster..."
# ===========================================================
# 🧱 BOILERPLATE SECTION — add your manifests below
# Example:
# oc apply -f ./manifests/namespace.yaml
# oc apply -f ./manifests/configmap.yaml
# oc apply -k ./kustomize/overlays/prod
# ===========================================================
echo "(No manifests applied yet — add your oc apply commands above)"
echo

# ---- Function to get status ----
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

  echo "🔍 Checking ArgoCD Application: $app"

  while true; do
    read -r sync health <<<"$(get_status "$app")"

    if [ -z "$sync" ]; then
      echo "❌ Application '$app' not found in namespace '$NAMESPACE'."
      return 2
    fi

    if [[ "$sync" == "Synced" && "$health" == "Healthy" ]]; then
      echo "✅ $app is Synced and Healthy."
      return 0
    fi

    echo "⏳ $app -> Sync=$sync, Health=$health (waiting...)"
    sleep "$INTERVAL"

    elapsed=$(( $(date +%s) - start ))
    if (( elapsed >= TIMEOUT )); then
      echo "❌ Timeout reached for $app after ${TIMEOUT}s."
      return 1
    fi
  done
}

# ---- Wait for all specified ArgoCD apps ----
for app in "$@"; do
  wait_for_app "$app" || exit $?
done

echo "🎉 All specified applications are Synced and Healthy."
echo

# ---- Patch the OpenShift Console to add flightctl-plugin ----
echo "🧩 Patching OpenShift Console to include 'flightctl-plugin'..."

# Check if plugin is already present
if oc get "$CONSOLE_RESOURCE" -o jsonpath='{.spec.plugins}' | grep -q '"flightctl-plugin"'; then
  echo "✅ 'flightctl-plugin' is already present in spec.plugins"
else
  oc patch "$CONSOLE_RESOURCE" --type=json \
    -p='[{"op":"add","path":"/spec/plugins/-","value":"flightctl-plugin"}]'
  if [ $? -eq 0 ]; then
    echo "✅ Successfully added 'flightctl-plugin' to Console spec.plugins"
  else
    echo "❌ Failed to patch the Console resource."
    exit 3
  fi
fi

echo "🏁 Done."
