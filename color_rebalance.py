import os
import cv2
import numpy as np
import glob

# ───────────────────────────────────────────────────────────────────────────────
#                        U S E R-CONFIGURATION
# ───────────────────────────────────────────────────────────────────────────────

INPUT_DIR   = "/ships22/sds/goes/digitized/32A/vissr/1978/grid_aligned/aligned_output_vi_4/aligned_with_grid"
OUTPUT_DIR  = "/ships22/sds/goes/digitized/32A/vissr/1978/grid_aligned/aligned_output_vi_4/aligned_with_grid_colorbalanced"
os.makedirs(OUTPUT_DIR, exist_ok=True)

SHIFT_LOG   = os.path.join(OUTPUT_DIR, "shift_log.txt")

N_SAMPLES   = 17
LEFT_X      = 46
RIGHT_X     = 1970
SAMPLE_Y    = 27

# ───────────────────────────────────────────────────────────────────────────────

def target_values(n):
    return np.linspace(0, 255, n)

# precompute x‐positions: midpoints of 17 segments between LEFT_X and RIGHT_X
segment_len = (RIGHT_X - LEFT_X) / N_SAMPLES
xs = (LEFT_X + (np.arange(N_SAMPLES) + 0.5) * segment_len).astype(int)

# open shift log
with open(SHIFT_LOG, "w") as log:

    for filepath in sorted(glob.glob(os.path.join(INPUT_DIR, "*.png"))):
        img = cv2.imread(filepath)
        if img is None:
            log.write(f"{os.path.basename(filepath)}: FAILED TO LOAD\n")
            continue

        h, w = img.shape[:2]
        y = min(max(SAMPLE_Y, 0), h - 1)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        measured = gray[y, xs].astype(float)
        target = target_values(N_SAMPLES)
        diffs = target - measured
        avg_diff = np.mean(diffs)

        if avg_diff > 30:
            log.write(f"{filename}: {avg_diff:.2f}, adjusting to zero\n")
            print(f"{filename}: shift {avg_diff:.2f}, adjusting to zero")
            avg_diff = 0

        # apply brightness shift
        balanced = img.astype(np.float32) + avg_diff
        balanced = np.clip(balanced, 0, 255).astype(np.uint8)

        # save adjusted image
        filename = os.path.basename(filepath)
        out_path = os.path.join(OUTPUT_DIR, filename)
        cv2.imwrite(out_path, balanced)

        # log the shift
        log.write(f"{filename}: {avg_diff:.2f}\n")

        print(f"{filename}: shift {avg_diff:.2f}")

print("Done! Color‐balanced images in:", OUTPUT_DIR)
print("Shift log at:", SHIFT_LOG)
