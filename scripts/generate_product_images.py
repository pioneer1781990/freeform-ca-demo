"""Generate real product images via Vertex AI Imagen and overwrite the 1x1 placeholders in GCS."""
import os, sys, warnings, io
warnings.filterwarnings("ignore")

from google.cloud import bigquery, storage
import vertexai
from vertexai.preview.vision_models import ImageGenerationModel

PROJECT_ID = "new-project-495419"
DATASET    = "cymbal_retail"
BUCKET     = "new-project-495419-cymbal-retail"

bq  = bigquery.Client(project=PROJECT_ID)
gcs = storage.Client(project=PROJECT_ID).bucket(BUCKET)

vertexai.init(project=PROJECT_ID, location="us-central1")

# Try newest model first, fall back as needed
candidates = ["imagen-4.0-generate-001", "imagen-3.0-generate-002", "imagen-3.0-generate-001"]
model = None
for m in candidates:
    try:
        model = ImageGenerationModel.from_pretrained(m)
        print(f"Using model: {m}")
        break
    except Exception as e:
        print(f"  {m} unavailable: {e}")
if model is None:
    sys.exit("No Imagen model available.")

products = list(bq.query(f"""
    SELECT pi.product_id, p.name, p.brand, p.department, p.category
    FROM `{PROJECT_ID}.{DATASET}.product_images` pi
    JOIN `{PROJECT_ID}.{DATASET}.products` p ON pi.product_id = p.id
    ORDER BY p.retail_price DESC
""").result())

for row in products:
    prompt = (
        f"Studio product photography of '{row.name}', "
        f"brand {row.brand}, {row.department}'s {row.category.lower()}. "
        f"Clean white background, soft even lighting, centered, no text, "
        f"e-commerce catalog style, photorealistic."
    )
    print(f"[{row.product_id}] {row.name[:60]}")
    try:
        result = model.generate_images(
            prompt=prompt,
            number_of_images=1,
            aspect_ratio="1:1",
            safety_filter_level="block_few",
            person_generation="dont_allow",
        )
        if not result.images:
            print(f"   no image returned (safety filter?)")
            continue
        png_bytes = result.images[0]._image_bytes
        blob = gcs.blob(f"product_images/prod_{row.product_id}.png")
        blob.upload_from_string(png_bytes, content_type="image/png")
        print(f"   uploaded {len(png_bytes):,} bytes")
    except Exception as e:
        print(f"   error: {e}")

print("\nDone. Re-run OBJ.FETCH_METADATA in BQ to refresh size/content_type.")
