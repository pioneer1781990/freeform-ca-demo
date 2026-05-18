# Running the demo from GitHub Codespaces

No local install needed — everything runs in a browser-based Linux container.

## One-time setup (~5 min)

### 1. Launch the Codespace

1. Go to https://github.com/pioneer1781990/freeform-ca-demo
2. Click **Code → Codespaces tab → Create codespace on main**
3. Wait ~2 min while Codespaces installs Python 3.11, `gcloud`, `gh`, and runs `pip install -r requirements.txt`

When the VS Code interface loads in your browser, you're ready.

### 2. Authenticate to GCP (open a Codespaces terminal)

```bash
# Terminal: Cmd+J or View → Terminal
gcloud auth login --no-launch-browser
# Paste the long URL into a normal browser tab, sign in, paste the verification code back

gcloud auth application-default login --no-launch-browser
# Same browser-paste flow — this one gets the credentials our Python SDKs use

gcloud config set project new-project-495419
gcloud auth application-default set-quota-project new-project-495419
```

### 3. Set up `.env`

```bash
cp .env.example .env
# Open .env in the Codespaces editor (left file tree) and fill in:
#   PROJECT_ID=new-project-495419
#   PROJECT_NUMBER=802175491358
#   ANTHROPIC_API_KEY=<your fresh key>
```

Then load it:
```bash
source .env
```

### 4. (Skip if you're using the existing `new-project-495419`) Provision GCP

```bash
./setup_gcp.sh       # ~3 min — creates dataset, bucket, connection, model
./load_data.sh       # ~10 min — loads thelook + Olist + ObjectRef + graph
```

**The existing demo project already has all this done — skip both scripts.**

## Run the demo (every time)

```bash
source .env
./run_demo.sh
```

Codespaces will detect port 8501 and pop up a **"Open in Browser"** notification. Click it. The Streamlit app opens in a new tab at a URL like `https://<your-codespace>-8501.app.github.dev/`.

If the popup doesn't appear:
- Switch to the **Ports** tab (bottom of the Codespaces window)
- Find port `8501`
- Click the globe icon next to it → opens in browser

**To get to the Studio page**, append `/Studio` to the URL.

## Demo flow (same as local)

| # | Where | Type | Expected |
|---|---|---|---|
| 1 | Ask | `What was our revenue last month?` | Sales Agent, ~$405k |
| 2 | Ask | `How many rows are in orders_staging?` | Refused |
| 3 | Ask | `What's our late delivery rate this month?` | Asks for definition → paste it → re-asks → Promote |
| 4a-c | Ask | 3 CX questions | All freelance / hedged |
| 5 | Studio → Memory | Approve late_delivery promotion | |
| 6 | Studio → Recs | Check signals → Publish CX Agent | |
| 7 | Ask | `What's our average review score by payment type?` | Routes to CX Agent |
| 8 | Ask | Active customers + 👎 + correction "60 days, not 90" | |
| 9 | Studio → Memory | Approve 4-user convergence | |
| 10 | Ask | Active customers again | Different number |
| 11 | Ask | `Show me return claims with their evidence photos` | ObjectRef + images |
| 12 | Studio → Agents → expand "View details" on any answer | Close | |

**Paste for beat 3:**
> *Percentage of marketplace orders where order_delivered_customer_date is later than order_estimated_delivery_date. From the marketplace_orders table.*

## Stopping & restarting

- Restart Streamlit only: `pkill -9 -f 'streamlit run' && ./run_demo.sh`
- Stop the Codespace (saves your work, no compute charges): browser tab → close. Resume via github.com → Codespaces.
- Delete the Codespace: github.com/codespaces → click the ⋯ menu → Delete

## Troubleshooting

| Problem | Fix |
|---|---|
| `gcloud: command not found` | The devcontainer feature failed. Run: `curl -sSL https://sdk.cloud.google.com \| bash; exec bash` |
| Streamlit port not auto-forwarded | Ports tab → right-click 8501 → set visibility to "Public" |
| `ANTHROPIC_API_KEY not set` | You forgot to `source .env`. Run it again. |
| Agent answers very slow first time | CA API cold-start is ~17s. Subsequent calls are cached |
| 403 on `bigquery-public-data` | Dataset must be in `US` multi-region. Re-source `.env`, re-run `setup_gcp.sh` |

## Codespaces quotas

- **Free tier**: 60 core-hours/month (2-core Codespace = 30h)
- Each Codespace running = burns hours. Stop when not using.
- For demo day: start ~10 min before showtime, keep alive through the demo, stop after.
