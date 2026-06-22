# OpenShell gateway sidecar for kartograph-api (Kubernetes compute driver).
FROM quay.io/fedora/fedora:44 AS tools
RUN dnf install -y openshell-gateway && dnf clean all

FROM registry.access.redhat.com/ubi9/ubi-minimal:latest

COPY --from=tools /usr/bin/openshell-gateway /usr/bin/openshell-gateway
COPY --from=tools /usr/share/openshell-gateway /usr/share/openshell-gateway

USER 65532:65532

ENTRYPOINT ["/usr/bin/openshell-gateway"]
