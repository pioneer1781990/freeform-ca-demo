# Freeform CA Demo — Cymbal Retail

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://github.com/codespaces/new?repo=pioneer1781990/freeform-ca-demo&ref=main)

> **🚀 To run the demo, click the badge above** — full launch steps in **[START_HERE.md](START_HERE.md)**.

A demo of the **Conversational Analytics (CA) API on BigQuery**, built as a self-improving "flywheel" for a fictional retailer (Cymbal Retail). Shows agent routing, glossary-driven hedging, memory feedback loops, ObjectRef for unstructured data, BQ Property Graph, and progressive recommendations.

Two surfaces:
- **Ask** (business user) — Gemini-Enterprise-styled chat
- **Studio** (analyst) — BQ-Studio-styled flywheel dashboard with recommendations

## How to start

| Where | Doc | TL;DR |
|---|---|---|
| Browser (Codespaces) — **recommended for the demo** | [START_HERE.md](START_HERE.md) | Click the Codespaces badge above |
| Browser (Codespaces) — detailed | [CODESPACES.md](CODESPACES.md) | Full terminal commands |
| Local laptop | Section below | `./run_demo.sh` after one-time setup |

## Quick start (local install)

```bash
git clone https://github.com/<you>/freeform-ca-demo.git
cd freeform-ca-demo

# 1. Prereqs (one-time)
#    - gcloud SDK installed + `gcloud auth login`
#    - bq, gsutil on PATH
#    - GCP project with billing enabled, you are Owner
#    - Kaggle account + ~/.kaggle/kaggle.json
#    - Anthropic API key

# 2. Configure
cp .env.example .env
# Edit .env — set PROJECT_ID, PROJECT_NUMBER, ANTHROPIC_API_KEY
source .env

# 3. Python venv + deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. Provision GCP (dataset, bucket, connection, model, glossary)
chmod +x setup_gcp.sh load_data.sh run_demo.sh
./setup_gcp.sh
# Copy CONNECTION_SA from the output back into .env, then re-source

# 5. Load all data (~10 min — includes Imagen image generation)
./load_data.sh

# 6. Start the demo
./run_demo.sh

# Ask     → http://localhost:8501/
# Studio  → http://localhost:8501/Studio
```

## Demo script (run-of-show)

| # | Where | Type | Expected |
|---|---|---|---|
| 1 | Ask | `What was our revenue last month?` | Routes to Sales Agent, ~$405k |
| 2 | Ask | `How many rows are in orders_staging?` | Refused (not agent_ready) |
| 3 | Ask | `What's our late delivery rate this month?` | Asks for definition → you paste → re-asks → answer → Promote button |
| 4a | Ask | `Average review score by product category` | Freelance with hedging |
| 4b | Ask | `Which sellers have the worst reviews?` | Freelance with hedging |
| 4c | Ask | `How many late deliveries did we have this quarter?` | Freelance, uses your definition |
| 5 | Studio → Memory | Approve `late_delivery_definition` | Promoted to glossary |
| 6 | Studio → Recommendations | Check for signals → Publish CX Agent | CX agent created in CA API |
| 7 | Ask | `What's our average review score by payment type?` | Routes to new CX agent |
| 8 | Ask | `How many active customers do we have right now?` | Sales agent (90-day rule). Thumbs-down + correction: `We define active as 60 days, not 90.` |
| 9 | Studio → Memory | Approve `active_customer_definition` (4 users converge) | Glossary updated |
| 10 | Ask | `How many active customers do we have right now?` | Different number (60-day rule), context shows promoted term |
| 11 | Ask | `Show me return claims with their evidence photos` | ObjectRef row with images |
| 12 | Studio → Agents | Show 2 published agents · expand any answer's "View details" | Output contract close |

**For late delivery in step 3, paste:**
> *Percentage of marketplace orders where order_delivered_customer_date is later than order_estimated_delivery_date. From the marketplace_orders table.*

## What lives in BigQuery

- **18 production tables** (4 sales, 5 CX, 4 supply chain, 4 VoC + 4 ObjectRef tables + 1 remote model)
- **4 dev/staging tables** labeled `agent_ready: false`
- **1 BQ Property Graph** (Customer → Product → DC)
- **Flywheel substrate** (prefix `_flywheel_*`): glossary, verified queries, agents, memory, query log, prep recs

## What lives in GCS

- `reviews/` — 30 Portuguese review snippets
- `support/` — 8 email/chat/phone transcripts
- `return_evidence/` — 2 customer-uploaded damage descriptions
- `product_images/` — 8 Imagen-generated product photos (PNG)
- `olist/` — source CSVs

## Architecture

```
app.py                        Streamlit entry → redirects to Ask
pages/
  1_💬_Ask.py                 Business user (Gemini Enterprise style)
  2_⚙️_Studio.py              Analyst (BQ Studio style)
core/
  orchestrator.py             Scope → glossary gap → agent route → freelance
  ca_api_client.py            CA SDK + Claude API fallback
  substrate.py                BQ reads (metadata, flywheel state, INFORMATION_SCHEMA)
  flywheel.py                 Writes (memory, glossary, agent publish, prep apply)
  confidence.py               Heuristic scoring
  output_contract.py          Answer + Citation dataclasses
  session.py                  Demo-session timestamp tracking
scripts/
  phase_a_data.sql            Sales + supply chain + VoC DDL
  phase_a_labels.sql          agent_ready labels
  phase_b_olist.sql           Olist descriptions
  phase_c_objectref.sql       ObjectRef tables
  phase_c_graph.sql           Property graph
  phase_c_flywheel.sql        Flywheel substrate + verified queries + memory seed
  generate_unstructured.py    Upload text files for ObjectRef
  generate_product_images.py  Imagen → 8 product PNGs
  retry_suspenders.py         Imagen safety-filter retry
  seed_query_log.py           100-row historical query log seed
  precreate_sales_agent.py    Pre-create Sales Agent + seed sales glossary
```

## Operational notes

- **Region constraint:** Dataset must be in `US` multi-region because `bigquery-public-data.thelook_ecommerce` only allows cross-region reads from `US`. Bucket can stay in `us-central1`.
- **CA API SDK version drift:** `google-cloud-geminidataanalytics` ≥0.12 expects `published_context` / `staging_context` on `DataAnalyticsAgent`, and `BigQueryTableReferences` (not `BigQueryDatasourceReferences`). Code is aligned with v0.12.0.
- **Streaming buffer:** Tables written via `insert_rows_json` block DELETE/UPDATE for ~30 min. Use `INSERT INTO ... SELECT` (DML) for upserts; the `register_agent_locally` path does this.
- **Agent latency:** CA chat in `THINKING` mode = ~70s. Set to `FAST` mode → ~17s. First call is unwarmed; subsequent are cached.
- **Imagen safety filters:** "suspenders" and other clothing-on-person prompts get rejected. `retry_suspenders.py` reframes with flat-lay prompts.

## Costs (rough, 1 demo session)

- BigQuery: <$1 (mostly free-tier query bytes; thelook copies = ~250MB)
- GCS: <$0.01/month for ~50MB of objects
- Vertex AI: ~$0.04 per Imagen image × 8 = $0.32 one-time
- Gemini 2.5 Flash via CA API: ~$0.01 per question × 30 questions = $0.30
- Claude Sonnet API: ~$0.02 per freelance call × 10 = $0.20

**Total per demo: under $2.**

## Teardown

```bash
# Stop the app
pkill -9 -f "streamlit run"

# Delete BQ dataset + GCS bucket + connection (irreversible)
bq rm -r -f -d ${PROJECT_ID}:${DATASET}
gsutil -m rm -r gs://${GCS_BUCKET}
bq rm -f --connection --location=${REGION} ${CONNECTION_ID}
gcloud dataplex glossaries delete cymbal-retail-glossary --location=${GCS_REGION} --quiet
```

## Credits

Cymbal Retail use case & demo flow — Siya. Built May 2026 against `google-cloud-geminidataanalytics` v0.12.0, `claude-sonnet-4-5-20250929`, Streamlit ≥1.39.
