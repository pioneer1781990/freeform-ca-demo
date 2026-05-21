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

| # | Where | Type | Expected behavior |
|---|---|---|---|
| 1 | Ask | `What was our revenue last month?` | Routes to **Sales Analytics** agent. Returns ~$405k with table + SQL. |
| 2 | Ask | `How many rows are in orders_staging?` | **Refused** — not labeled `agent_ready`. |
| 3 | Ask | `What's our late delivery rate this month?` | Asks you to define "late delivery". **Paste** the definition below. Then auto re-asks. Click **Promote to team** on the green banner. |
| 4a | Ask | `Average review score by product category` | Freelance with hedging |
| 4b | Ask | `Which sellers have the worst reviews?` | Freelance with hedging |
| 4c | Ask | `How many late deliveries did we have this quarter?` | Freelance, uses your definition |
| 5 | Studio → Memory | Click **Approve & promote** on `late_delivery_definition` | Becomes a glossary term |
| 6 | Studio → Recommendations | Click **🔁 Check for signals** → click **Review & publish** on the CX Agent proposal | CX agent created in CA API |
| 7 | Ask | `What's our average review score by payment type?` | Routes to the new **CX** agent. 95% confidence. |
| 8 | Ask | `How many active customers do we have right now?` → **👎** → correction: `We define active as 60 days, not 90.` | Personal memory saved |
| 9 | Studio → Memory | Click **Approve & promote** on `active_customer_definition` (4-user convergence: Alice, Bob, Carol, you) | Glossary updated |
| 10 | Ask | `How many active customers do we have right now?` *(re-ask)* | Different number — uses the 60-day rule |
| 11 | Ask | `Show me return claims with their evidence photos` | ObjectRef row with images |
| 12 | Studio → Agents (close) | Show 2 published agents. Switch to Ask, expand "View details" on any answer. | The output contract — narrative, SQL, citations, confidence, all portable. |

### Definitions to paste when the system asks for one

Pick the one matching whatever term the system says it doesn't know:

**Late delivery** (used in step 3):
```
Percentage of marketplace orders where order_delivered_customer_date is later than order_estimated_delivery_date. From the marketplace_orders table.
```

**CSAT** (if you ask a CSAT question instead):
```
Percentage of customer reviews where review_score >= 4. From the customer_reviews table. Higher is better.
```

**Stockout** (if you ask about stockout risk):
```
A product is at stockout risk when current qty_on_hand in inventory_snapshots is less than or equal to its reorder_point.
```

**Days of supply** (if you ask about DOS):
```
Days of supply = qty_on_hand / avg_daily_demand from the last 30 days of inventory_snapshots.
```

**Active customer** correction (for step 8 thumbs-down):
```
We define active as 60 days, not 90.
```

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
