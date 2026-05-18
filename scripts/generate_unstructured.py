"""Generate unstructured GCS files for ObjectRef demo."""
import os
import warnings
warnings.filterwarnings("ignore")

from google.cloud import bigquery, storage

PROJECT_ID = "new-project-495419"
DATASET = "cymbal_retail"
BUCKET = "new-project-495419-cymbal-retail"

bq = bigquery.Client(project=PROJECT_ID)
gcs = storage.Client(project=PROJECT_ID)
bucket = gcs.bucket(BUCKET)

# 1. Review text files (Portuguese)
print("Pulling review texts from BQ...")
reviews = list(bq.query(f"""
    SELECT review_id, review_comment_message
    FROM `{PROJECT_ID}.{DATASET}.customer_reviews`
    WHERE review_comment_message IS NOT NULL
      AND LENGTH(review_comment_message) > 30
    LIMIT 30
""").result())
print(f"Uploading {len(reviews)} review files...")
for row in reviews:
    blob = bucket.blob(f"reviews/{row.review_id}.txt")
    blob.upload_from_string(row.review_comment_message, content_type='text/plain')

# 2. Support ticket documents
tickets = [
    ("TKT001", "email", "Subject: Late delivery\n\nI placed order #10001 over two weeks ago and tracking still shows 'processing'. This is unacceptable. I need this for an event this weekend. Please expedite or refund immediately.\n\nRegards, Customer"),
    ("TKT002", "chat", "Agent: Hi, how can I help?\nCustomer: I got the wrong size. Ordered Medium, got XL.\nAgent: I'm sorry about that. Let me initiate an exchange.\nCustomer: How long will the replacement take?\nAgent: 5-7 business days.\nCustomer: That's too long. Can you overnight it?\nAgent: Let me check with shipping..."),
    ("TKT003", "phone", "Call Summary:\nCustomer reported receiving a damaged product (cracked cosmetics palette). Customer was visibly frustrated. Offered full refund + 20% discount on next order. Customer accepted. Photo evidence requested and received. Escalated to quality team for supplier review."),
    ("TKT004", "email", "Subject: Refund not processed\n\nI returned my order 3 weeks ago (tracking confirms delivery to your warehouse on April 28). I still haven't received my refund of $127.50. Your policy says 5-7 business days. It's been 15. Please process immediately or I will file a chargeback.\n\nOrder #10004"),
    ("TKT005", "chat", "Customer: The jacket looks nothing like the photos. The color is totally off.\nAgent: I apologize for the discrepancy. Could you share a photo?\nCustomer: [photo attached] See? It's supposed to be navy, this is practically grey.\nAgent: I can see the difference. Let me process a return for you."),
    ("TKT006", "email", "Subject: Missing item\n\nMy order #10006 was supposed to include 3 items but only 2 arrived. The missing item is the leather belt (SKU: BLT-442). Packing slip shows all 3 items. Please ship the missing item ASAP."),
    ("TKT007", "phone", "Call Summary:\nCustomer called to compliment the fast delivery and product quality. Mentioned they've been a customer for 2 years and appreciate the recent improvements in packaging. No action required. Logged as positive feedback."),
    ("TKT008", "email", "Subject: When will my order ship?\n\nOrder #10008 placed May 14. Status still says 'processing'. Expected delivery was May 16. Is there a delay? Please update me.\n\nThank you"),
]
print(f"Uploading {len(tickets)} support ticket docs...")
for tid, channel, content in tickets:
    blob = bucket.blob(f"support/{tid}_{channel}.txt")
    blob.upload_from_string(content, content_type='text/plain')

# 3. Return evidence placeholder text files (representing photo descriptions)
returns = [
    ("CLM001", "Photo: damaged cosmetics palette, visible crack across lower-right corner. Box exterior shows crushing damage on left side. Bubble wrap insufficient."),
    ("CLM002", "Photo: jacket color is light grey under natural light. Listing shows navy blue. Side-by-side with phone screen confirms mismatch."),
]
print(f"Uploading {len(returns)} return evidence docs...")
for cid, desc in returns:
    blob = bucket.blob(f"return_evidence/{cid}.txt")
    blob.upload_from_string(desc, content_type='text/plain')

# 4. Product images: placeholder 1x1 PNG (8 products)
PNG_1x1 = bytes([
    0x89,0x50,0x4E,0x47,0x0D,0x0A,0x1A,0x0A,0x00,0x00,0x00,0x0D,0x49,0x48,0x44,0x52,
    0x00,0x00,0x00,0x01,0x00,0x00,0x00,0x01,0x08,0x06,0x00,0x00,0x00,0x1F,0x15,0xC4,
    0x89,0x00,0x00,0x00,0x0D,0x49,0x44,0x41,0x54,0x78,0x9C,0x63,0x00,0x01,0x00,0x00,
    0x05,0x00,0x01,0x0D,0x0A,0x2D,0xB4,0x00,0x00,0x00,0x00,0x49,0x45,0x4E,0x44,0xAE,
    0x42,0x60,0x82
])
product_ids = list(bq.query(f"SELECT id FROM `{PROJECT_ID}.{DATASET}.products` LIMIT 8").result())
print(f"Uploading {len(product_ids)} placeholder product images...")
for row in product_ids:
    blob = bucket.blob(f"product_images/prod_{row.id}.png")
    blob.upload_from_string(PNG_1x1, content_type='image/png')

print("All unstructured files uploaded.")
