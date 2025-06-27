import os
import glob
import cv2
import numpy as np

# ───────────────────────────────────────────────────────────────────────────────
# USER–CONFIGURATION (SHAPE FILTERING LOGIC)
# ───────────────────────────────────────────────────────────────────────────────
# --- Input/Output Files ---
INPUT_DIR = "/ships22/sds/goes/digitized/14A/vissr/1977/grid_aligned/aligned_output_vi/aligned_with_grid/0N75.5W"
GLOB_PATTERN = "14*.png"  # Adjust to your file naming pattern
OUT_FILE_COMPOSITE = os.path.join(INPUT_DIR, "composite_clean.png")
OUT_FILE_MASK = os.path.join(INPUT_DIR, "detected_features_mask.png")
OUT_FILE_OVERLAY = os.path.join(INPUT_DIR, "detected_features_overlay.png")

# --- Top-Hat Filter Parameters ---
# This remains the primary tuning parameter for initial feature detection.
# A larger kernel is less sensitive to texture and better for finding lines on a varied background.
TOPHAT_KERNEL_SIZE = (70, 70)

# --- NEW: Shape-Based Filtering Parameters ---
# Any contour with an area smaller than this will be considered noise and discarded.
MIN_CONTOUR_AREA = 2
# Any contour that fills up more than this fraction of its bounding box will be
# considered a "blob" (like a landmass) and discarded. This is the key parameter.
MAX_EXTENT = 4


# ───────────────────────────────────────────────────────────────────────────────
# Main Execution Logic
# ───────────────────────────────────────────────────────────────────────────────

def main():
    """
    Main function to run the image processing pipeline.
    """
    print("1) Gathering and loading images...")
    paths = sorted(glob.glob(os.path.join(INPUT_DIR, GLOB_PATTERN)))
    if not paths:
        raise RuntimeError(f"No images found in {INPUT_DIR} matching {GLOB_PATTERN}")

    imgs_color = [cv2.imread(p, cv2.IMREAD_COLOR) for p in paths]

    print("2) Creating a clean composite image...")
    clean_composite_color = create_simple_composite(imgs_color)
    cv2.imwrite(OUT_FILE_COMPOSITE, clean_composite_color)
    print(f"   -> Clean composite saved to {OUT_FILE_COMPOSITE}")

    gray_composite = cv2.cvtColor(clean_composite_color, cv2.COLOR_BGR2GRAY)

    print("3) Isolating bright features with Top-Hat filter...")
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, TOPHAT_KERNEL_SIZE)
    tophat_result = cv2.morphologyEx(gray_composite, cv2.MORPH_TOPHAT, kernel)

    print("4) Thresholding to create candidate feature mask...")
    _, binary_mask = cv2.threshold(tophat_result, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    print("5) Filtering features by SHAPE to remove blobs...")
    final_mask = np.zeros_like(binary_mask)
    contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    line_like_contours = []
    for cnt in contours:
        # --- Shape Analysis ---
        area = cv2.contourArea(cnt)

        # 1. Filter out tiny noise specks
        if area < MIN_CONTOUR_AREA:
            continue

        # 2. Filter out blobs using Extent
        x, y, w, h = cv2.boundingRect(cnt)
        bounding_box_area = w * h
        if bounding_box_area == 0: continue  # Avoid division by zero

        extent = float(area) / bounding_box_area

        if extent > MAX_EXTENT:
            continue  # This contour is a blob, so we discard it

        # If the contour passes all checks, it's line-like
        line_like_contours.append(cnt)

    # Draw the final, filtered contours onto our mask
    cv2.drawContours(final_mask, line_like_contours, -1, 255, -1)

    print(f"6) Saving final mask and overlay...")
    cv2.imwrite(OUT_FILE_MASK, final_mask)
    print(f"   -> Final feature mask saved to {OUT_FILE_MASK}")

    overlay_img = create_overlay(clean_composite_color, final_mask)
    cv2.imwrite(OUT_FILE_OVERLAY, overlay_img)
    print(f"   -> Overlay image saved to {OUT_FILE_OVERLAY}")


def create_simple_composite(imgs_color):
    """Creates a simple average of all images."""
    accumulator = np.zeros(imgs_color[0].shape, dtype=np.float64)
    for img in imgs_color:
        accumulator += img.astype(np.float64)
    avg_img = accumulator / len(imgs_color)
    return avg_img.astype(np.uint8)


def create_overlay(background_img, mask):
    """Overlays the detected mask in red on top of a background image."""
    color_mask = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    color_mask[np.where((color_mask == [255, 255, 255]).all(axis=2))] = [0, 0, 255]  # BGR Red
    overlay = cv2.addWeighted(background_img, 0.7, color_mask, 0.9, 0)
    return overlay


if __name__ == "__main__":
    main()