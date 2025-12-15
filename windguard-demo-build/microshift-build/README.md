# Building the MicroShift device image

In this section, we are going to build the

export OCP_CLUSTER_DOMAIN=ocp.ocpdemo.labs
subscription-manager repos --enable rhacm-2.15-for-rhel-9-x86_64-rpms --enable rhocp-4.20-for-rhel-9-x86_64-rpms

dnf install flightctl container-tools openshift-clients -y

cd windguard-demo-build/microshift-build/

podman login quay.io --authfile=auth.json
podman login registry.redhat.io --authfile=auth.json

oc login -u admin -p openshift https://api.$OCP_CLUSTER_DOMAIN:6443

oc get secret/pull-secret -n openshift-config --template='{{index .data ".dockerconfigjson" | base64decode}}' > pull-secret


export RHEM_API_SERVER_URL=$(oc get route -n open-cluster-management flightctl-api-route -o json | jq -r .spec.host)
flightctl login --username=admin --password=openshift https://$RHEM_API_SERVER_URL


[root@rhel9-server microshift-build]# flightctl version
Client Version: v0.10.0
Server Version: v0.10.0


export BOOTC_IMAGE=quay.io/kubealex/windguard-microshift:edgemanager

sed -i "s|BOOTC_IMAGE|$BOOTC_IMAGE|g" rhem-fleet.yml

[root@rhel9-server microshift-build]# flightctl apply -f rhem-fleet.yml
fleet: applying rhem-fleet.yml/fleet-acm: 200 OK


flightctl certificate request --signer=enrollment --expiration=365d --output=embedded > config.yaml

export REGISTRY_URL=quay.io REGISTRY_USER=kubealex
podman build --rm --no-cache -t $REGISTRY_URL/$REGISTRY_USER/windguard-microshift:latest .
podman push $REGISTRY_URL/$REGISTRY_USER/windguard-microshift:latest

podman build --rm --no-cache -t $REGISTRY_URL/$REGISTRY_USER/windguard-microshift:ocpvirt-qcow2 -f Containerfile.ocpvirt .
podman push $REGISTRY_URL/$REGISTRY_USER/windguard-microshift:ocpvirt-qcow2

podman run --rm -it --privileged --pull=newer \
    --security-opt label=type:unconfined_t \
    -v "${PWD}/output":/output \
    -v /var/lib/containers/storage:/var/lib/containers/storage \
    registry.redhat.io/rhel9/bootc-image-builder:latest \
    --type qcow2 \
    $REGISTRY_URL/$REGISTRY_USER/windguard-microshift:latest

podman build --rm --no-cache -t $REGISTRY_URL/$REGISTRY_USER/windguard-microshift:ocpvirt-qcow2 -f Containerfile.ocpvirt .
podman push $REGISTRY_URL/$REGISTRY_USER/windguard-microshift:ocpvirt-qcow2

export QCOW_IMAGE=$REGISTRY_URL/$REGISTRY_USER/windguard-microshift:ocpvirt-qcow2

oc apply -f windguard-namespace.yml
sed -i "s|QCOW_IMAGE|$QCOW_IMAGE|g" windguard-vm-ocpvirt.yml
oc apply -f windguard-vm.yml
virt-install \
    --name rhel-bootc-vm \
    --vcpus 4 \
    --memory 4096 \
    --import --disk ./output/qcow2/disk.qcow2,format=qcow2 \
    --os-variant rhel10.0 \
    --network network=default