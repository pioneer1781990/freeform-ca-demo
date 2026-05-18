#!/usr/bin/env bash
# One-shot GCP + BigQuery + GCS provisioning for the Freeform CA demo.
# Idempotent: re-running is safe.
#
# Prereqs: gcloud authed, bq + gsutil installed, billing enabled on PROJECT_ID
#
# Usage:
#   source .env
#   ./setup_gcp.sh

set -euo pipefail
: "${PROJECT_ID:?PROJECT_ID not set — source your .env first}"
: "${REGION:=US}"
: "${GCS_REGION:=us-central1}"
: "${DATASET:=cymbal_retail}"
: "${GCS_BUCKET:=${PROJECT_ID}-cymbal-retail}"
: "${CONNECTION_ID:=cymbal-gcs-conn}"

echo "▶ Setting project to $PROJECT_ID"
gcloud config set project "$PROJECT_ID" 2>&1 | tail -1

echo "▶ Enabling APIs (may take 30s if first time)"
gcloud services enable \
  bigquery.googleapis.com bigqueryconnection.googleapis.com \
  geminidataanalytics.googleapis.com cloudaicompanion.googleapis.com \
  dataplex.googleapis.com storage.googleapis.com \
  aiplatform.googleapis.com 2>&1 | tail -3

echo "▶ Setting ADC quota project"
gcloud auth application-default set-quota-project "$PROJECT_ID" 2>&1 | tail -1 || true

echo "▶ Creating BigQuery dataset (in $REGION multi-region — needed for thelook public-data reads)"
bq --location=$REGION mk --dataset --description="Cymbal Retail Freeform CA demo" \
   "${PROJECT_ID}:${DATASET}" 2>&1 | tail -1 || echo "  (dataset already exists)"

echo "▶ Creating GCS bucket in $GCS_REGION"
gsutil mb -l $GCS_REGION -p "$PROJECT_ID" "gs://${GCS_BUCKET}/" 2>&1 | tail -1 || echo "  (bucket already exists)"

echo "▶ Creating Cloud Resource Connection for ObjectRef"
bq mk --connection --connection_type=CLOUD_RESOURCE --location=$REGION \
   --project_id=$PROJECT_ID "$CONNECTION_ID" 2>&1 | tail -1 || echo "  (connection already exists)"

echo "▶ Granting connection SA permissions"
CONN_SA=$(bq --project_id=$PROJECT_ID show --connection --format=json "${REGION,,}.${CONNECTION_ID}" 2>/dev/null \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['cloudResource']['serviceAccountId'])")
echo "  SA: $CONN_SA"
gsutil iam ch "serviceAccount:${CONN_SA}:objectViewer" "gs://${GCS_BUCKET}/" 2>&1 | tail -1
gcloud projects add-iam-policy-binding "$PROJECT_ID" --condition=None \
  --member="serviceAccount:${CONN_SA}" --role="roles/aiplatform.user" 2>&1 | tail -1

echo "▶ Creating remote Gemini model for AI.GENERATE_TEXT (may take ~30s on IAM propagation)"
sleep 10
bq query --project_id=$PROJECT_ID --use_legacy_sql=false --location=$REGION \
  "CREATE OR REPLACE MODEL \`${DATASET}.gemini_model\` REMOTE WITH CONNECTION \`${REGION,,}.${CONNECTION_ID}\` OPTIONS (ENDPOINT = 'gemini-2.5-flash')" \
  2>&1 | tail -2 || echo "  (model creation may need a retry after IAM propagation)"

echo "▶ Creating Dataplex glossary shell"
gcloud dataplex glossaries create cymbal-retail-glossary \
  --project=$PROJECT_ID --location=$GCS_REGION \
  --display-name="Cymbal Retail Glossary" \
  --description="Business glossary for Cymbal Retail analytics" 2>&1 | tail -2 || echo "  (glossary already exists)"

echo "✓ GCP setup complete. Run ./load_data.sh next."
echo "  Connection SA (save to .env if not already there):"
echo "  CONNECTION_SA=$CONN_SA"
