# OpenShell gateway sidecar for kartograph-api (Kubernetes compute driver).
# Uses the official NVIDIA OpenShell gateway release binary (v0.0.83).
#
# Must be >= v0.0.72 (NVIDIA/OpenShell#2009): earlier releases hardcode the
# Kubernetes driver's Sandbox API group/version to agents.x-k8s.io/v1alpha1
# with no fallback. v0.0.72+ detects the served version at runtime (trying
# v1beta1 first, then v1alpha1), which is required once the Agent Sandbox
# CRD on a cluster only serves v1beta1 — the failure mode otherwise is every
# sandbox list/watch call erroring with a raw "404 page not found" (not a
# structured NotFound Status), which is what broke Graph Management
# Assistant session start in kartograph-stage.
FROM registry.access.redhat.com/ubi9/ubi-minimal:latest

ARG OPENSHELL_VERSION=0.0.83

RUN microdnf install -y ca-certificates gzip tar \
    && curl -fsSL -o /tmp/openshell-gateway-x86_64-unknown-linux-gnu.tar.gz \
      "https://github.com/NVIDIA/OpenShell/releases/download/v${OPENSHELL_VERSION}/openshell-gateway-x86_64-unknown-linux-gnu.tar.gz" \
    && curl -fsSL -o /tmp/openshell-gateway-checksums-sha256.txt \
      "https://github.com/NVIDIA/OpenShell/releases/download/v${OPENSHELL_VERSION}/openshell-gateway-checksums-sha256.txt" \
    && (cd /tmp && grep " openshell-gateway-x86_64-unknown-linux-gnu.tar.gz$" openshell-gateway-checksums-sha256.txt | sha256sum -c -) \
    && tar xzf /tmp/openshell-gateway-x86_64-unknown-linux-gnu.tar.gz -C /usr/local/bin \
    && chmod 755 /usr/local/bin/openshell-gateway \
    && rm -f /tmp/openshell-gateway-x86_64-unknown-linux-gnu.tar.gz /tmp/openshell-gateway-checksums-sha256.txt \
    && microdnf clean all

RUN mkdir -p /var/openshell \
    && chmod -R g+rwX /var/openshell

USER 65532:65532

ENTRYPOINT ["/usr/local/bin/openshell-gateway"]
