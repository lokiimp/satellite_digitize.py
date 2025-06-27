import os
import glob
import cv2
import numpy as np

# ───────────────────────────────────────────────────────────────────────────────
#                        USER–CONFIGURATION
# ───────────────────────────────────────────────────────────────────────────────
INPUT_DIR = "/ships22/sds/goes/digitized/14A/vissr/1977/grid_aligned/aligned_output_vi/aligned_with_grid/0N75.5W"  # change to your folder
GLOB_EXT  = ("*.png", "*.jpg", "*.jpeg")
TH_THRESH = 110     # threshold for “bright”
MAX_DELTA = 45      # max grayscale spread allowed
MIN_FRAC  = 0.70    # require ≥80% of images
OUT_FILE  = os.path.join(INPUT_DIR, "composite.png")

# ───────────────────────────────────────────────────────────────────────────────
# 1) Gather image paths
paths = []
for ext in GLOB_EXT:
    paths.extend(sorted(glob.glob(os.path.join(INPUT_DIR, ext))))
if not paths:
    raise RuntimeError(f"No images found in {INPUT_DIR}")

# 2) Load and verify sizes
imgs_color = [cv2.imread(p, cv2.IMREAD_COLOR) for p in paths]
h, w = imgs_color[0].shape[:2]
for img in imgs_color:
    if img.shape[:2] != (h, w):
        raise RuntimeError("All images must have the same dimensions")

# 3) Build grayscale stack and bright‐mask stack
N = len(imgs_color)
stack_gray = np.stack([
    cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.int16)
    for img in imgs_color
], axis=0)  # shape: (N, H, W)
bright_mask = (stack_gray > TH_THRESH)  # shape: (N, H, W)

# 4) Count how many are bright at each pixel
bright_count = bright_mask.sum(axis=0)    # (H, W)
min_needed   = int(np.ceil(MIN_FRAC * N))
enough_bright = bright_count >= min_needed  # (H, W) bool

# 5) For pixels with enough bright images, check stability
#    Compute per-pixel max/min among *only* those bright images
#    We'll set non-bright to NaN to ignore them in min/max
gray_float = stack_gray.astype(np.float32)
masked_gray = np.where(bright_mask, gray_float, np.nan)  # (N,H,W)
gmax = np.nanmax(masked_gray, axis=0)  # (H, W)
gmin = np.nanmin(masked_gray, axis=0)
stable = (gmax - gmin) <= MAX_DELTA

# 6) Final keep mask: enough bright *and* stable
keep = enough_bright & stable  # (H, W)

# 7) Composite color: average only the pixels from images where bright_mask=True
stack_col = np.stack(imgs_color, axis=0).astype(np.float32)  # (N,H,W,3)
# expand bright_mask to (N,H,W,1) to mask colors
bm4 = bright_mask[..., None]
# zero out non-bright
masked_col = np.where(bm4, stack_col, np.nan)  # nan for excluded
# sum and count
sum_col = np.nansum(masked_col, axis=0)  # (H,W,3)
count_col = np.sum(bright_mask, axis=0)[..., None]  # (H,W,1)
avg_col = sum_col / np.maximum(count_col, 1)        # avoid div/0

# 8) Build the output: black background, fill kept pixels
composite = np.zeros((h, w, 3), dtype=np.uint8)
for c in range(3):
    channel = np.clip(avg_col[..., c], 0, 255).astype(np.uint8)
    composite[..., c][keep] = channel[keep]

# 9) Save
cv2.imwrite(OUT_FILE, composite)
print(f"Composite saved to {OUT_FILE}")
