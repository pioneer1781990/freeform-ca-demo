# START HERE — How to launch the demo

You have two ways to run this:

| | When to use |
|---|---|
| **A. GitHub Codespaces** (browser) | Demo day. No local install. Recommended. |
| **B. Local laptop** | If you want to iterate on the code with your own editor |

---

## A. Run from GitHub Codespaces (browser)

### One-click launch

**👉 [Click here to open in Codespaces](https://github.com/codespaces/new?repo=pioneer1781990/freeform-ca-demo&ref=main)**

Wait ~2 min for the container to provision and `pip install -r requirements.txt` to finish (you'll see logs at the bottom).

### Authenticate (one-time per Codespace)

Open a terminal in Codespaces (`Cmd+J` on Mac, `Ctrl+\`` elsewhere) and paste:

```bash
gcloud auth login --no-launch-browser
gcloud auth application-default login --no-launch-browser
gcloud config set project new-project-495419
gcloud auth application-default set-quota-project new-project-495419
```

Each `gcloud auth ...` command prints a long URL. Copy it into a normal browser tab, sign in with the GCP account that owns the project, copy the verification code, paste it back into the Codespaces terminal.

### Add your Anthropic API key

```bash
cp .env.example .env
```

In the file tree on the left, click **`.env`** to open it. Replace `ANTHROPIC_API_KEY=sk-ant-api03-...` with your real key. Save (`Cmd+S`).

Then in the terminal:

```bash
source .env
```

### Start the demo

```bash
./run_demo.sh
```

When you see:
```
✓ Freeform CA demo is live
  Ask     →  http://localhost:8501/
  Studio  →  http://localhost:8501/Studio
```

Codespaces will pop up **"Your application running on port 8501 is available"** in the bottom right — click **"Open in Browser"**.

> If no popup: click the **Ports** tab at the bottom → find port `8501` → click the 🌐 globe icon.

### Demo URLs

The URL you opened (e.g. `https://name-8501.app.github.dev/`) is the **Ask** page. Open a second tab with `/Studio` appended for the analyst view.

---

## B. Run on your local laptop

Already provisioned (you ran this earlier):

```bash
cd "/Users/vasiyakrishnan/BQ demos/freeform_demo"
source .env
source .venv/bin/activate
./run_demo.sh
```

Opens at http://localhost:8501/ and http://localhost:8501/Studio

For a fresh laptop, see [README.md → Quick start (local install)](README.md#quick-start-local-install).

---

## The demo script — questions to ask in order

| # | Action | Expected behavior |
|---|---|---|
| 1 | Click chip: `What was our revenue last month?` | Routes to **Sales Analytics** agent. ~$405k. Citation shows agent rule + Net Revenue glossary. |
| 2 | Click chip: `What's our late delivery rate by month?` | Routes to **Customer Experience** agent. Answers cleanly because the agent's `system_instruction` encodes the late-delivery rule. Citations show the agent rule + a `INFORMATION_SCHEMA.JOBS` verified query pattern. |
| 3 | Click chip: `What's our customer churn rate?` | **Disambiguation flow** — system asks you to pick one of 4 churn definitions (90 days / 60 days / 12 months / single-purchase). Click **"No purchase in the last 90 days"**. Answer appears (38.4%) with the citation crediting your choice. In **Studio (right panel)** a new recommendation card appears: *"Promote 'churn' (90-day rule) to Dataplex glossary"*. Click **"Save to Dataplex glossary"** in Studio → green toast → "Built today" gains an entry. |
| 4 | Click chip: `Average review score by Brazilian state` | CX agent **partial answer** at lower confidence — it didn't have a verified template, so it mined 3 historical query patterns from `JOBS`. Studio gets a new rec: *"Promote 3 query-history patterns to CX agent"*. Click **"Promote to CX agent"** in Studio → real `UpdateDataAgent` call → the patterns become `example_queries` on the CX agent (visible in BQ Studio). |
| 5 | Type in chat: `For our top 10 customers, which distribution centers stock the products they buy?` | Freelance attempts the 3-table join and hedges. Studio gets: *"Add edges to BQ Property Graph"*. Click **"Add to graph"** in Studio → real `CREATE OR REPLACE PROPERTY GRAPH` runs → the graph extends from 2 nodes/1 edge to 3 nodes/2 edges (visible in BigQuery). Re-ask the same question → clean graph-traversal answer. |
| 6 | Type in chat: `What are customers most upset about in their reviews?` | Keyword-only shallow answer (misses Portuguese). Studio gets: *"Create vector embeddings on review_comment_message"*. Click **"Create embeddings"** in Studio → ~10s of real `ML.GENERATE_EMBEDDING` over 500 reviews → embeddings table created (visible in BigQuery). Re-ask → semantic theme clusters with Portuguese terms (`atraso`, `quebrado`, `cor errada`). |
| 7 | **Inheritance moment.** At top of Ask page, switch user dropdown from **Siya** to **Alex**. Then ask `What's our customer churn rate?` again. | Alex never disambiguated, never defined anything — but the answer arrives instantly (~1.5s) with the same 38.4%, and the citation credits *"🧠 Inherited: glossary term 'churn' defined by Siya, May 21"*. Same trick for the other 3 questions (review by state, top customers/DCs, customers most upset) — Alex inherits all of Siya's enrichments. |
| 8 | Close: scroll **Studio** to see "Built today" — list of every artifact added this session. | Glossary term in Dataplex · CX agent example_queries · Graph extended · Embeddings table. All real, all visible in GCP console tabs. |

### Definitions / picks reference

**Beat 3 — Churn disambiguation:** Click the **"No purchase in the last 90 days"** option. The other three options also work — each produces a different but equally valid answer (45.7% for 60-day, 22.1% for 12-month, 51.3% for single-purchase). Stick with 90-day for the script.

**If you ad-lib a question and the system asks for an inline definition**, here are pre-written ones:

| Term | Definition to paste |
|---|---|
| CSAT | Percentage of customer reviews where review_score >= 4. From the customer_reviews table. Higher is better. |
| Stockout | A product is at stockout risk when current qty_on_hand in inventory_snapshots is less than or equal to its reorder_point. |
| Days of supply | qty_on_hand / avg_daily_demand from the last 30 days of inventory_snapshots. |

---

## Between dry runs

Reset session signal counter so beat 6 re-fires fresh:

- Studio → Recommendations tab → **Reset session** button

Or from terminal:

```bash
rm /tmp/freeform_session_start.txt
pkill -9 -f "streamlit run" && ./run_demo.sh
```

---

## Troubleshooting on demo day

| Symptom | Fix |
|---|---|
| Agent answer takes 30+ seconds | Normal cold start. Pre-warm by asking "What is total revenue?" once before going live. |
| "Codespaces is starting" hangs | Refresh the browser tab; Codespaces resumes where it left off. |
| `ANTHROPIC_API_KEY not set` | You forgot `source .env`. Run it again. |
| Port 8501 shows blank | `pkill -9 -f streamlit && ./run_demo.sh` |
| "promotion_requested column not found" | One-time fix: `bq query --location=US "ALTER TABLE \`new-project-495419.cymbal_retail._flywheel_memory\` ADD COLUMN IF NOT EXISTS promotion_requested BOOL"` |
| CX agent publish hangs | It's the CA API IAM-propagation lag. Wait 30s, click again. |

---

## Stop the Codespace when done

GitHub → your profile menu → **Codespaces** → click ⋯ next to the active codespace → **Stop**. (You can resume later without losing state. Delete only when truly done — keeping it stopped is free.)
