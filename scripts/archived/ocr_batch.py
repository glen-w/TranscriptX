import os
from pathlib import Path
from PIL import Image, ImageOps
from transformers import TrOCRProcessor, VisionEncoderDecoderModel

INPUT_DIR = Path("/Users/89298/Desktop/test_input")
OUTPUT_DIR = Path("/Users/89298/Desktop/test_output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("🧠 Loading TrOCR large handwritten model...")
processor = TrOCRProcessor.from_pretrained("microsoft/trocr-large-handwritten")
model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-large-handwritten")

image_files = sorted(INPUT_DIR.glob("*.[jp][pn]g"))

for img_file in image_files:
    try:
        print(f"🔍 Processing {img_file.name}...")

        # Open image in RGB and enhance
        image = Image.open(img_file).convert("RGB")
        image = ImageOps.autocontrast(image)

        # OCR
        pixel_values = processor(images=image, return_tensors="pt").pixel_values
        generated_ids = model.generate(pixel_values)
        transcription = processor.batch_decode(generated_ids, skip_special_tokens=True)[
            0
        ]

        # Save output
        output_path = OUTPUT_DIR / (img_file.stem + ".txt")
        with open(output_path, "w") as f:
            f.write(transcription)

        print(f"✅ Saved to {output_path.name}")
    except Exception as e:
        print(f"❌ Failed to process {img_file.name}: {e}")
