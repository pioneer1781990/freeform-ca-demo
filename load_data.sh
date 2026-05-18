#!/usr/bin/env bash
# Load all data: thelook tables, synthetic tables, Olist, ObjectRef, graph, flywheel substrate.
# Run AFTER setup_gcp.sh succeeds.

set -euo pipefail
: "${PROJECT_ID:?source .env first}"
: "${REGION:=US}"
: "${DATASET:=cymbal_retail}"
: "${GCS_BUCKET:=${PROJECT_ID}-cymbal-retail}"

echo "▶ 1/7  Loading thelook (sales + supply chain) + synthetic VoC tables"
bq query --project_id=$PROJECT_ID --use_legacy_sql=false --location=$REGION < scripts/phase_a_data.sql > /dev/null
echo "  ✓ thelook + synthetic loaded"

echo "▶ 2/7  Applying agent_ready labels"
bq query --project_id=$PROJECT_ID --use_legacy_sql=false --location=$REGION < scripts/phase_a_labels.sql > /dev/null
echo "  ✓ labels applied"

echo "▶ 3/7  Downloading Olist via Kaggle"
mkdir -p ~/olist_data
[ -f ~/.kaggle/kaggle.json ] || { echo "  ✗ ~/.kaggle/kaggle.json missing"; exit 1; }
chmod 600 ~/.kaggle/kaggle.json
source .venv/bin/activate 2>/dev/null || true
kaggle datasets download -d olistbr/brazilian-ecommerce -p ~/olist_data/ --unzip 2>&1 | tail -2
gsutil -m cp ~/olist_data/olist_*.csv gs://${GCS_BUCKET}/olist/ 2>&1 | tail -2
for pair in "customer_reviews:olist_order_reviews_dataset.csv" "customer_payments:olist_order_payments_dataset.csv" "marketplace_sellers:olist_sellers_dataset.csv" "marketplace_orders:olist_orders_dataset.csv" "marketplace_customers:olist_customers_dataset.csv"; do
  T="${pair%%:*}"; F="${pair##*:}"
  EXTRA=""
  [ "$T" = "customer_reviews" ] && EXTRA="--allow_quoted_newlines=true --max_bad_records=100"
  bq load --location=$REGION --source_format=CSV --autodetect --replace --skip_leading_rows=1 $EXTRA \
    "${PROJECT_ID}:${DATASET}.${T}" "gs://${GCS_BUCKET}/olist/${F}" > /dev/null 2>&1
  echo "  ✓ $T"
done

echo "▶ 4/7  Applying Olist labels + descriptions"
bq query --project_id=$PROJECT_ID --use_legacy_sql=false --location=$REGION < scripts/phase_b_olist.sql > /dev/null
echo "  ✓ Olist labels applied"

echo "▶ 5/7  Uploading unstructured GCS files (reviews, support, return evidence, placeholder images)"
python3 scripts/generate_unstructured.py 2>&1 | tail -5

echo "▶ 6/7  Generating real product images via Imagen (~3 min, 8 images)"
python3 scripts/generate_product_images.py 2>&1 | tail -10
python3 scripts/retry_suspenders.py 2>&1 | tail -2 || true

echo "▶ 7/7  Creating ObjectRef tables, BQ Graph, flywheel substrate, seed query log"
bq query --project_id=$PROJECT_ID --use_legacy_sql=false --location=$REGION < scripts/phase_c_objectref.sql > /dev/null
bq query --project_id=$PROJECT_ID --use_legacy_sql=false --location=$REGION < scripts/phase_c_graph.sql > /dev/null
bq query --project_id=$PROJECT_ID --use_legacy_sql=false --location=$REGION < scripts/phase_c_flywheel.sql > /dev/null
python3 scripts/seed_query_log.py 2>&1 | tail -2
echo "  ✓ All data + substrate ready"

echo ""
echo "✓ Data load complete. Run ./run_demo.sh to start the app."
