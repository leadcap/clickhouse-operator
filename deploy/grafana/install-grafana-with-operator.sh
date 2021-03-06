#!/bin/bash

GRAFANA_NAMESPACE="${GRAFANA_NAMESPACE:-grafana}"

GRAFANA_NAME="${GRAFANA_NAME:-grafana}"
GRAFANA_ADMIN_USER="${GRAFANA_ADMIN_USER:-admin}"
GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-admin}"
GRAFANA_DISABLE_LOGIN_FORM="${GRAFANA_DISABLE_LOGIN_FORM:-False}"
GRAFANA_DISABLE_SIGNOUT_MENU="${GRAFANA_DISABLE_SIGNOUT_MENU:-True}"

GRAFANA_DATA_SOURCE_NAME="${GRAFANA_DATA_SOURCE_NAME:-chdatasource}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://prometheus.prometheus:9090}"

GRAFANA_DASHBOARD_NAME="${GRAFANA_DASHBOARD_NAME:-chdashboard}"

########################################
##                                    ##
## Install Grafana as Custom Resource ##
##                                    ##
########################################


kubectl apply --namespace="${GRAFANA_NAMESPACE}" -f <( \
    cat grafana-cr-template.yaml | \
    GRAFANA_NAME="$GRAFANA_NAME" \
    GRAFANA_ADMIN_USER="$GRAFANA_ADMIN_USER" \
    GRAFANA_ADMIN_PASSWORD="$GRAFANA_ADMIN_PASSWORD" \
    GRAFANA_DISABLE_LOGIN_FORM="$GRAFANA_DISABLE_LOGIN_FORM" \
    GRAFANA_DISABLE_SIGNOUT_MENU="$GRAFANA_DISABLE_SIGNOUT_MENU" \
    envsubst \
)

echo "Waiting to start"
sleep 60

kubectl apply --namespace="${GRAFANA_NAMESPACE}" -f <( \
    cat grafana-data-source-cr-template.yaml | \
    GRAFANA_DATA_SOURCE_NAME="$GRAFANA_DATA_SOURCE_NAME" \
    PROMETHEUS_URL="$PROMETHEUS_URL" \
    envsubst \
)

echo "Waiting to start"
sleep 60

kubectl apply --namespace="${GRAFANA_NAMESPACE}" -f <( \
    cat grafana-dashboard-cr-template.yaml | \
    GRAFANA_DASHBOARD_NAME="$GRAFANA_DASHBOARD_NAME" \
    envsubst \
)
