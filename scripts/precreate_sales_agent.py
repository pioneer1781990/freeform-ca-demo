"""Pre-create the Sales Agent in CA API + register locally + seed Sales glossary terms.
Run once before the demo."""
import warnings; warnings.filterwarnings("ignore")
import sys
sys.path.insert(0, ".")
from core import flywheel, substrate
import config as cfg

SALES_SYS = """You are the Cymbal Retail Sales Analytics Agent. Answer questions about direct ecommerce sales using these tables: orders, order_items, products, users.

Key business rules:
- Revenue = SUM(order_items.sale_price). EXCLUDE rows where status IN ('Cancelled','Returned').
- cost in products is the wholesale cost to Cymbal. retail_price is MSRP, NOT the actual sale price.
- Gross Margin = (sale_price - cost) / sale_price.
- department is either 'Men' or 'Women'.
- Active Customer = a user with at least one non-Cancelled, non-Returned order in the last 90 days (unless overridden by user memory).
- AOV (Average Order Value) = SUM(sale_price) / COUNT(DISTINCT order_id), same exclusions.
- Return Rate = COUNTIF(status='Returned') / COUNT(*).

When filtering TIMESTAMP columns (orders.created_at, order_items.created_at) use TIMESTAMP_TRUNC / TIMESTAMP_SUB — never DATE_TRUNC / DATE_SUB."""

SALES_TABLES = ["orders","order_items","products","users"]
SALES_GLOSSARY = [
    ("Net Revenue", "SUM(order_items.sale_price) excluding Cancelled and Returned items."),
    ("Active Customer", "User with at least one non-Cancelled, non-Returned order in the last 90 days."),
    ("AOV", "Average Order Value = Net Revenue / COUNT(DISTINCT order_id)."),
    ("Return Rate", "COUNTIF(order_items.status='Returned') / COUNT(*)."),
    ("Gross Margin", "(order_items.sale_price - products.cost) / order_items.sale_price."),
]

fw = flywheel.get()
print("Pre-seeding 5 Sales glossary terms...")
existing = set(substrate.get().glossary()['term'].str.lower()) if not substrate.get().glossary().empty else set()
for term, defn in SALES_GLOSSARY:
    if term.lower() in existing:
        print(f"  skip (exists): {term}")
        continue
    fw.add_glossary_term(term, defn, source="precreated_with_sales_agent")
    print(f"  added: {term}")

print()
print("Publishing Sales Agent to CA API + flywheel...")
ok = fw.publish_agent(
    agent_id=cfg.PRECREATED_AGENT_ID,
    name="Sales Analytics",
    description="Direct ecommerce sales, customer base, and product analytics across orders, order_items, products, users.",
    tables_in_scope=SALES_TABLES,
    glossary_terms=[t for t,_ in SALES_GLOSSARY],
    system_instruction=SALES_SYS,
)
print(f"CA API publish ok: {ok}")
print("Done.")
