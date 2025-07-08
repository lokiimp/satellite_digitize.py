import os
import cv2
import numpy as np
import re

# Configuration
YEAR = 1977
INPUT_DIR = "/ships22/sds/goes/digitized/32A/vissr/1977/grid_aligned/aligned_output_vi_2/aligned_no_grid_nobg"
MARBLE_PATH = "/ships22/sds/goes/digitized/masks/marble135w.png"
OUTPUT_DIR = "/ships22/sds/goes/digitized/32A/vissr/1977/grid_aligned/aligned_output_vi_2/fakecolor"
OUTPUT_VIDEO = "/ships22/sds/goes/digitized/32A/vissr/1977/grid_aligned/aligned_output_vi_2/1977_west_fake_color.mp4"

BRIGHTNESS_THRESHOLD = 180
FPS = 10

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Load background image
marble = cv2.imread(MARBLE_PATH)
if marble is None:
    raise FileNotFoundError(f"Cannot load marble background from {MARBLE_PATH}")

# Match size to input images
sample_img = cv2.imread(next((os.path.join(INPUT_DIR, f) for f in os.listdir(INPUT_DIR) if f.endswith('.png')), None))
if sample_img is None:
    raise FileNotFoundError(f"No input images found in {INPUT_DIR}")
if marble.shape[:2] != sample_img.shape[:2]:
    marble = cv2.resize(marble, (sample_img.shape[1], sample_img.shape[0]))

# Sort files by DOY using regex (e.g., 32A.1976.001....png)
def extract_doy(filename):
    m = re.search(rf"\.{YEAR}\.(\d{{3}})\.", filename)
    return int(m.group(1)) if m else float('inf')

files = sorted(
    [f for f in os.listdir(INPUT_DIR) if f.endswith(".png")],
    key=extract_doy
)

frames = []

for fname in files:
    img_path = os.path.join(INPUT_DIR, fname)
    img = cv2.imread(img_path)
    if img is None:
        print(f"Skipping unreadable file: {fname}")
        continue

    # Convert to grayscale and threshold
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, BRIGHTNESS_THRESHOLD, 255, cv2.THRESH_BINARY)

    # Make mask 3-channel
    mask_3ch = cv2.merge([mask, mask, mask])

    # Keep only cloud pixels from original
    clouds = cv2.bitwise_and(img, mask_3ch)

    # Overlay clouds onto marble
    combined = cv2.addWeighted(marble, 1.0, clouds, 1.0, 0)

    # Save to folder
    out_path = os.path.join(OUTPUT_DIR, fname)
    cv2.imwrite(out_path, combined)
    frames.append(combined)

    print(f"Processed {fname}")

# Make video
if frames:
    height, width, _ = frames[0].shape
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    video = cv2.VideoWriter(OUTPUT_VIDEO, fourcc, FPS, (width, height))
    for frame in frames:
        video.write(frame)
    video.release()
    print(f"Video saved as {OUTPUT_VIDEO}")
else:
    print("No frames were processed; video not created.")
