import cv2
import numpy as np
import glob
import os

# ──────────────────────────────────────────────────────────────────────────────
# USER SETTINGS
IMG_FOLDER = "input_images/"           # Folder containing all your input PNGs
OUTPUT_PATH = f"images/static_overlay_mask.png"
THRESHOLD_BRIGHT = 180                 # any pixel >180 will be “white overlay”
MORPH_KERNEL_SIZE = 3                  # for optional noise cleanup
DILATE_ITERATIONS = 1                  # to ensure thin lines are connected
# ──────────────────────────────────────────────────────────────────────────────

# 1) FIND ALL PNG FILES IN IMG_FOLDER
image_files = sorted(glob.glob(os.path.join(IMG_FOLDER, "*.png")))
if len(image_files) == 0:
    raise RuntimeError(f"No PNGs found in {IMG_FOLDER!r}")

# 2) LOAD THE FIRST IMAGE TO GET TARGET DIMENSIONS & CENTER
sample = cv2.imread(image_files[0])
if sample is None:
    raise RuntimeError(f"Could not load {image_files[0]}")
height, width = sample.shape[:2]
center_target = (width // 2, height // 2)

# This function returns (cx, cy) = the pixel‐coordinates of the globe's center
def find_globe_center(img_bgr):
    """
    1) Convert to grayscale, threshold to separate outer black background.
    2) Invert, find largest contour, and compute its centroid.
    3) Return (cx, cy). If something fails, return (width/2, height/2) as fallback.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    # ANY pixel darker than 10 is almost certainly “background outside the globe.”
    _, thresh_inv = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY_INV)

    contours, _ = cv2.findContours(thresh_inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return center_target

    big = max(contours, key=lambda c: cv2.contourArea(c))
    M = cv2.moments(big)
    if abs(M["m00"]) < 1e-3:
        return center_target

    cx = int(M["m10"] / M["m00"])
    cy = int(M["m01"] / M["m00"])
    return (cx, cy)


# 3) LOOP OVER ALL IMAGES, ALIGN + THRESHOLD + STORE THE OVERLAY MASK
all_masks = []  # will hold one binary mask per image

for img_path in image_files:
    img = cv2.imread(img_path)
    if img is None or img.shape[:2] != (height, width):
        raise RuntimeError(f"Image {img_path!r} missing or wrong size. All must be {height}×{width}.")

    # 3a) Find this image’s globe center
    (cx_img, cy_img) = find_globe_center(img)

    # 3b) Compute how far to shift (to bring this center → target_center)
    dx = center_target[0] - cx_img
    dy = center_target[1] - cy_img

    # 3c) Warp (translate) the image by (dx, dy)
    M_trans = np.float32([[1, 0, dx],
                          [0, 1, dy]])
    aligned = cv2.warpAffine(img, M_trans, (width, height), flags=cv2.INTER_LINEAR)

    # 3d) Convert to grayscale & threshold to isolate bright grid/text/outline pixels
    gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, THRESHOLD_BRIGHT, 255, cv2.THRESH_BINARY)

    # 3e) (Optional) Clean small speckle using MORPH_OPEN/CLOSE
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (MORPH_KERNEL_SIZE, MORPH_KERNEL_SIZE))
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=1)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel, iterations=1)

    # 3f) Dilate once so that even thin gridlines become fully covered
    dil_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    final_mask = cv2.dilate(cleaned, dil_kernel, iterations=DILATE_ITERATIONS)

    all_masks.append(final_mask)

    print(f"  • Processed {os.path.basename(img_path)} → found {np.count_nonzero(final_mask)} white overlay pixels.")

# 4) COMPUTE PIXEL-WISE AND ACROSS ALL MASKS
# Initialize intersection_mask = the first image’s mask, then AND with each subsequent
intersection_mask = all_masks[0].copy()
for m in all_masks[1:]:
    intersection_mask = cv2.bitwise_and(intersection_mask, m)

# 5) SAVE THE RESULT
cv2.imwrite(OUTPUT_PATH, intersection_mask)
print(f"\nSaved static overlay mask (intersection of {len(all_masks)} images) as:\n  {OUTPUT_PATH}")
