import warnings; warnings.filterwarnings("ignore")
from google.cloud import storage
import vertexai
from vertexai.preview.vision_models import ImageGenerationModel

vertexai.init(project="new-project-495419", location="us-central1")
model = ImageGenerationModel.from_pretrained("imagen-4.0-generate-001")

prompts = [
    "Studio product photo of black men's suspenders, 1.5 inch wide elastic with metal clip ends, "
    "laid flat on a white background, no person, no model, e-commerce catalog style, top-down view.",
    "Flat-lay photograph of a pair of black suspenders with silver clips, isolated on pure white "
    "background, product photography, no person.",
    "Black elastic suspenders with metal hardware, isolated product shot, white background, "
    "no human figure, retail catalog.",
]
gcs = storage.Client(project="new-project-495419").bucket("new-project-495419-cymbal-retail")

for i, p in enumerate(prompts, 1):
    print(f"Attempt {i}: {p[:70]}...")
    try:
        r = model.generate_images(prompt=p, number_of_images=1, aspect_ratio="1:1",
                                  safety_filter_level="block_few", person_generation="dont_allow")
        if r.images:
            b = r.images[0]._image_bytes
            gcs.blob("product_images/prod_28405.png").upload_from_string(b, content_type="image/png")
            print(f"   ✓ uploaded {len(b):,} bytes"); break
        print("   empty result")
    except Exception as e:
        print(f"   {e}")
