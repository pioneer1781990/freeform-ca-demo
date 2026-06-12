# Freeform CA Demo — Handoff Document

Comprehensive reference for the Cymbal Retail demo built May 17–21, 2026.
Pick this up cold and have a working demo running in <5 minutes.

---

## What this demo proves

A "self-improving" Conversational Analytics layer on BigQuery, where:

- Business users ask questions in natural language
- The system shows its work (citations, reasoning, agent rules applied)
- When questions expose gaps, the system **notifies an analyst** rather than guessing
- The analyst applies fixes — glossary terms in **Dataplex**, verified queries on the **CX agent**, edges on a **BQ Property Graph**, and **vector embeddings** on text columns
- All fixes are real, visible in GCP console, and persist
- Subsequent users (different personas) **inherit** the prior fixes — the flywheel grows, never resets

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      Streamlit single-page app                   │
├──────────────────────────────────────────────────────────────────┤
│  ASK (left, 60%)                  STUDIO (right, 40%)            │
│  ─ persona switcher               ─ live signals (JOBS history)  │
│  ─ suggestion chips               ─ recommendations              │
│  ─ chat + answer rendering        ─ apply actions                │
│  ─ citations + SQL                ─ "Built today" trail          │
│  ─ no action buttons              ─ Reset (wipes GCP too)        │
└──────────────────────────────────────────────────────────────────┘

backend modules (core/):
  orchestrator.py     — scope → route → freelance fallback
  answer_cache.py     — pre-cached responses matching real CA API shape
  ca_api_client.py    — google.cloud.geminidataanalytics SDK wrapper
  flywheel.py         — glossary writes, verified-query promotion, provenance
  dataplex_ops.py     — direct REST to dataplex.googleapis.com glossary terms
  graph_ops.py        — CREATE OR REPLACE PROPERTY GRAPH
  embeddings_ops.py   — ML.GENERATE_EMBEDDING + VECTOR_SEARCH
  live_signals.py     — INFORMATION_SCHEMA-style cards for Studio
  user_switcher.py    — Siya / Alex / Morgan personas + inheritance logic
  output_contract.py  — Answer dataclass returned to every caller
  session.py          — start-timestamp file for "current session" scoping
```

---

## Demo questions (in order, 4–5 min total)

| # | Type or click | Agent | Reaction in Studio |
|---|---|---|---|
| 1 | `What was our revenue last month?` | Sales Analytics | none |
| 2 | `What's our late delivery rate by month?` | CX (uses agent instruction + JOBS pattern) | none |
| 3 | `What's our customer churn rate?` | (asks user to pick from 4 churn defs) | **Promote 'churn' to Dataplex glossary** |
| 4 | `Average review score by Brazilian state` | CX agent partial; reconstructs from JOBS | **Promote 3 query patterns to CX agent** |
| 5 | `For our top 10 customers, which distribution centers stock the products they buy?` | Freelance, fails | **Add DC edges to BQ Property Graph** |
| 6 | `What are customers most upset about in their reviews?` | Keyword-only shallow | **Create vector embeddings on review_comment_message** |
| 7 | Switch persona to Alex, re-ask 3 / 4 / 5 / 6 | Inherited from Siya | none — already enriched |

**Aliases that also hit cache:** "monthly revenue", "churn rate", "review by state", "customer complaints", "top customers and distribution centers".

---

## Real artifacts created during demo

| Action | Where it lands | How to verify |
|---|---|---|
| Save to Dataplex | `cymbal-retail-glossary/terms/<slug>` + `_flywheel_glossary` BQ row | `gcloud dataplex glossaries describe cymbal-retail-glossary` or REST GET on terms |
| Promote to CX agent | `cymbal_customer_experience_agent_12ba.published_context.example_queries` | BQ Studio → Data Agents → click the agent → "Verified queries (3)" |
| Add to graph | `cymbal_retail_graph` rebuilt with DC node + StockedAt edge | BQ Studio → Graphs → cymbal_retail_graph → see 3 nodes, 2 edges |
| Create embeddings | `cymbal_retail.review_embeddings` table + `gemini_text_embed` model | BQ Studio → tables → review_embeddings |

Reset button (in Studio) wipes all four cleanly.

---

## How to run

### Local (recommended for live demo)

```bash
cd "/Users/vasiyakrishnan/BQ demos/freeform_demo"
source .venv/bin/activate
source .env
./run_demo.sh
# opens at http://localhost:8501
```

Reset between dry runs: click **"↺ Reset demo"** in Studio (wipes app + GCP state).

### GitHub Codespaces (portable)

1. https://github.com/codespaces/new?repo=pioneer1781990/freeform-ca-demo&ref=main
2. In terminal:
   ```bash
   curl -sSL https://sdk.cloud.google.com | bash && exec bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   gcloud auth login --no-launch-browser
   gcloud auth application-default login --no-launch-browser
   gcloud config set project new-project-495419
   gcloud auth application-default set-quota-project new-project-495419
   cp .env.example .env
   # edit .env: set ANTHROPIC_API_KEY, PROJECT_ID=new-project-495419
   source .env
   ./run_demo.sh
   ```
3. Click "Open in Browser" on port 8501 popup.

**Codespace can be stopped/resumed indefinitely — only ./run_demo.sh needs to re-run each session.**

---

## Recording (Fable / Loom / QuickTime)

For a polished walkthrough as backup or shareable artifact:

- **Fable** (app.fable.ai) is good if you want clean step annotations and the audience to see the flow as guided steps. Best for sharing async.
- **Loom** captures sequential narration with talking head. Best if you want voice + face.
- **QuickTime** is fast, no editing needed. Best for quick backup recording.

Pre-demo cleanup before recording:

1. Click **"↺ Reset demo"** in Studio — wait for green toast
2. Refresh GCP console tabs to confirm clean state
3. Open these 5 tabs left-to-right:
   - GCP Dataplex glossary (should be empty)
   - BQ Property Graph (2 nodes, 1 edge)
   - BQ table list (no `review_embeddings`)
   - BQ Data Agents → cymbal_customer_experience_agent_12ba (Verified queries: 0)
   - http://localhost:8501 (the app)
4. Start recording on the GCP tabs to show the empty "before" state
5. Switch to the app and walk through the 7 beats from the table above

Each enrichment click takes ~3s, embeddings ~10s. Plan ~5 min total.

---

## Key GCP details

| | Value |
|---|---|
| GCP Project | `new-project-495419` (project number `802175491358`) |
| BQ Location | `US` multi-region |
| GCS Bucket | `new-project-495419-cymbal-retail` (us-central1) |
| Connection | `us.cymbal-gcs-conn` |
| Dataplex glossary | `projects/new-project-495419/locations/us-central1/glossaries/cymbal-retail-glossary` |
| Sales Agent (pre-created) | `cymbal_sales_agent` |
| CX Agent (pre-created) | `cymbal_customer_experience_agent_12ba` |
| Remote model (text gen) | `cymbal_retail.gemini_model` → `gemini-2.5-flash` |
| Remote model (embeddings) | `cymbal_retail.gemini_text_embed` → `text-embedding-005` (created on click in Beat 6) |

---

## What's actually in BigQuery

Production tables under `cymbal_retail`:
- **Sales (thelook):** `orders`, `order_items`, `products`, `users`
- **CX (Olist):** `customer_reviews`, `customer_payments`, `marketplace_orders`, `marketplace_customers`, `marketplace_sellers`
- **Supply chain:** `distribution_centers`, `inventory_items`, `inventory_snapshots`, `supplier_catalog`
- **VoC:** `support_tickets`, `return_claims`
- **ObjectRef:** `review_docs`, `support_ticket_docs`, `return_evidence_docs`, `product_images`
- **Property Graph:** `cymbal_retail_graph` (baseline: Customer → Purchased → Product; extended in demo to add DC + StockedAt)
- **Dev/staging (labeled `agent_ready: false`, refused by scope check):** `orders_staging`, `products_dev`, `user_events_raw`, `tmp_analysis_20260510`

Flywheel state tables:
- `_flywheel_glossary` (5 pre-seeded Sales terms: Net Revenue, Active Customer, AOV, Return Rate, Gross Margin)
- `_flywheel_query_log` (100 pre-seeded historical analyst queries with clusters)
- `_flywheel_memory` (5 pre-seeded entries — Alice/Bob/Carol agree on active customer = 60 days)
- `_flywheel_verified_queries`, `_flywheel_agents`, `_flywheel_prep_recs` (mostly empty / seeded)
- `_demo_provenance` (tracks what was created during the demo for clean teardown)

---

## Known gotchas / non-obvious behavior

1. **CA API SDK is finicky.** `UpdateDataAgent` requires `update_mask` AND `_pb.ClearField('last_published_context')` before sending. The agent ID gets a 4-char time suffix on slug to avoid CA's 30-day tombstone on deleted IDs.

2. **Dataplex term API isn't in the Python SDK reliably** — uses direct REST against `dataplex.googleapis.com/v1/.../glossaries/.../terms`. The SDK's `BusinessGlossaryServiceClient` 404s.

3. **Streaming buffer issue.** Memory and feedback writes use SQL DML `INSERT` (not `insert_rows_json`) to avoid the 30-min lockout on subsequent UPDATE/DELETE.

4. **Cache aliases.** Phrasing variants like "churn rate" or "review by state" map to canonical cache keys. See `_ALIASES` in `core/answer_cache.py`.

5. **Inheritance keys.** `applied_enrichments` set tracks: `churn_defined`, `cx_verified_queries`, `graph_extended`, `embeddings_created`. When non-Siya user asks a matching question, suffix `[inherited-by-<user>-from-<key>]` is appended.

6. **Late delivery does NOT trigger needs_definition** — it's an agent-instruction beat (the CX agent's system_instruction encodes the rule).

7. **Churn IS ambiguous by design** — uses `needs_disambiguation` path with 4 options. After user picks, suffix is `[post-choose-<key>]` (90d/60d/1y/single).

8. **Reset demo** (the button in Studio):
   - Drops `review_embeddings` table + `gemini_text_embed` model
   - Resets graph to baseline (Customer → Product only)
   - Deletes Dataplex terms: churn, stockout, csat, days-of-supply
   - Clears CX agent's verified queries
   - Deletes `_flywheel_glossary` rows with `source IN ('manual','promoted_from_memory','defined_in_demo')`
   - All in one 5–8s spinner

---

## File map (what to edit when)

| To change | Edit |
|---|---|
| What a chip says or what's cached | `core/answer_cache.py` |
| Routing / which agent picks up a question | `core/orchestrator.py` (`_route_to_agent`) |
| Live signals cards in Studio | `core/live_signals.py` |
| New persona | `core/user_switcher.py` + add `[inherited-by-<id>-from-*]` variants to cache |
| Recommendation card UI | `app.py` (the `if rec["kind"] == ...` block) |
| Styling | `styles.py` (`BASE_CSS`) + inline `<style>` in `app.py` |
| New action wiring | `app.py` (`_apply_recommendation`) + ops module for the actual GCP work |

---

## Commits worth knowing

- `e7e652f` Codespaces uses universal:2-linux image (recovery-mode fix)
- `468da86` v2 architecture: business/analyst split + live signals + persona switcher
- `bb3a1e9` Fix CX agent UpdateDataAgent: requires `update_mask`
- `b842f6d` Fix `last_published_context` ClearField required before update
- `aad174e` Cache alias matching + normalized lookup
- `66d0d9d` Conversational definition flow (no inline textbox)
- `650235e` Reset demo wipes GCP state too
- `2dcae16` Graph baseline = Customer→Product only (so "Add to graph" produces visible change)

---

## If something is broken

1. Check `tail -50 /tmp/streamlit.log` for errors
2. Verify GCP auth: `gcloud auth list` shows your account active
3. Verify quota project: `gcloud config get-value project` → `new-project-495419`
4. Check CX agent exists: `gcloud dataplex glossaries list --location=us-central1` (different command for agents, but you get the idea — list whatever you think might be missing)
5. **Click Reset demo** — it's the nuclear option that cleans up almost everything

---

## Final demo arc (read aloud while clicking)

> *"Cymbal Retail has structured data across sales, CX, supply chain. Two pre-built CA agents — Sales Analytics, and Customer Experience. Watch what happens as a business user asks questions, and how the analyst's studio enriches the system in real time.*
>
> *Beat 1 — revenue. Routes to Sales agent, instant.*
>
> *Beat 2 — late delivery. The CX agent's system instruction defines exactly what late means. Same rule across teams.*
>
> *Beat 3 — churn is ambiguous. The system asks me to pick. I pick 90 days. Studio surfaces a recommendation: promote my pick to the Dataplex glossary. One click — and it's now in BigQuery and Dataplex, visible to everyone.*
>
> *Beat 4 — review by Brazilian state. The CX agent didn't have this template, so it reconstructed from query history. Studio recommends promoting those patterns as verified queries on the CX agent itself — one click and they're attached, visible in BQ Studio.*
>
> *Beat 5 — multi-hop question. Freelance struggles with a 4-table join. Studio recommends extending the graph. Click — the graph rebuilds with DC edges. Same question now traverses cleanly.*
>
> *Beat 6 — semantic question on Portuguese text. Keyword search misses everything. Studio recommends vector embeddings. Click, 10 seconds of real Vertex AI embedding generation, then the same question returns themed clusters in Portuguese.*
>
> *Beat 7 — switch user to Alex. Re-ask all four questions. Each comes back instantly with citations crediting Siya as the original enricher. Alex never had to do any of the curation work. The flywheel doesn't reset — it grows."*
