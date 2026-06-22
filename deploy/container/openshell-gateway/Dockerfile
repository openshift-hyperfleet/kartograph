# OpenShell gateway sidecar for kartograph-api (Kubernetes compute driver).
# Uses the official NVIDIA OpenShell gateway release binary (v0.0.62).
FROM registry.access.redhat.com/ubi9/ubi-minimal:latest

ARG OPENSHELL_VERSION=0.0.62

RUN microdnf install -y ca-certificates gzip tar \
    && curl -fsSL -o /tmp/openshell-gateway.tgz \
      "https://github.com/NVIDIA/OpenShell/releases/download/v${OPENSHELL_VERSION}/openshell-gateway-x86_64-unknown-linux-gnu.tar.gz" \
    && tar xzf /tmp/openshell-gateway.tgz -C /usr/local/bin \
    && chmod 755 /usr/local/bin/openshell-gateway \
    && rm -f /tmp/openshell-gateway.tgz \
    && microdnf clean all

RUN mkdir -p /var/openshell \
    && chmod -R g+rwX /var/openshell

USER 65532:65532

ENTRYPOINT ["/usr/local/bin/openshell-gateway"]
