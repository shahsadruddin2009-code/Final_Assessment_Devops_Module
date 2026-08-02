#!/bin/bash
set -euo pipefail

NAMESPACE="default"

echo "Applying Kubernetes manifests..."
kubectl apply -f k8s/configmap.yaml -n "${NAMESPACE}"
kubectl apply -f k8s/postgres.yaml -n "${NAMESPACE}"

echo "Waiting for the database to be available..."
kubectl rollout status deployment/northwind-postgres -n "${NAMESPACE}" --timeout=120s

kubectl apply -f k8s/deployment.yaml -n "${NAMESPACE}"
kubectl apply -f k8s/service.yaml -n "${NAMESPACE}"

echo "Waiting for deployment to be available..."
kubectl rollout status deployment/northwind-delivery -n "${NAMESPACE}" --timeout=120s

echo "Running smoke tests..."
kubectl delete job northwind-smoke-test -n "${NAMESPACE}" --ignore-not-found=true
kubectl apply -f k8s/smoke-test.yaml -n "${NAMESPACE}"
kubectl wait --for=condition=complete --timeout=60s job/northwind-smoke-test -n "${NAMESPACE}"

echo "Smoke test logs:"
kubectl logs job/northwind-smoke-test -n "${NAMESPACE}"
