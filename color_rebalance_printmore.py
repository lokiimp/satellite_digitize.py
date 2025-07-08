import os
import cv2
import numpy as np
import glob

# ───────────────────────────────────────────────────────────────────────────────
#                        USER–CONFIGURATION
# ───────────────────────────────────────────────────────────────────────────────

INPUT_DIR    = "/ships22/sds/goes/digitized/32A/vissr/1977/grid_aligned/aligned_output_vi_2/aligned_with_grid"
OUTPUT_DIR   = "/ships22/sds/goes/digitized/32A/vissr/1977/grid_aligned/aligned_output_vi_2/aligned_with_grid_colorbalanced"
DEBUG_DIR    = "/ships22/sds/goes/digitized/32A/vissr/1977/grid_aligned/aligned_output_vi_2/aligned_with_grid_debug_bar"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DEBUG_DIR,  exist_ok=True)

SHIFT_LOG    = os.path.join(OUTPUT_DIR, "shift_log.txt")

N_SAMPLES    = 17
LEFT_X       = 55
RIGHT_X      = 1960
SAMPLE_Y     = 27

# ───────────────────────────────────────────────────────────────────────────────

def target_values(n):
    return np.linspace(0, 255, n)

# precompute x‐positions: midpoints of 17 segments between LEFT_X and RIGHT_X
segment_len = (RIGHT_X - LEFT_X) / N_SAMPLES
xs = (LEFT_X + (np.arange(N_SAMPLES) + 0.5) * segment_len).astype(int)

# open shift log
with open(SHIFT_LOG, "w") as log:

    for filepath in sorted(glob.glob(os.path.join(INPUT_DIR, "*.png"))):
        filename = os.path.basename(filepath)

        # load image
        img = cv2.imread(filepath)
        if img is None:
            log.write(f"{filename}: FAILED TO LOAD\n")
            print(f"{filename}: FAILED TO LOAD")
            continue

        # ensure SAMPLE_Y is valid
        h, w = img.shape[:2]
        y = min(max(SAMPLE_Y, 0), h - 1)

        # convert to grayscale and sample
        gray     = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        measured = gray[y, xs].astype(float)
        target   = target_values(N_SAMPLES)
        diffs    = target - measured

        # zero out any individual shift > 30
        diffs[np.abs(diffs) > 30] = 0

        avg_diff = np.mean(diffs)

        # --- save debug overlay ---
        debug_img = img.copy()
        # horizontal green line at y
        cv2.line(debug_img,
                 (LEFT_X, y),
                 (RIGHT_X, y),
                 (0, 255, 0),
                 2)
        # green dots at each sample location
        for x in xs:
            cv2.circle(debug_img,
                       (int(x), y),
                       5, (0, 255, 0), -1)
        # write debug image
        cv2.imwrite(os.path.join(DEBUG_DIR, filename), debug_img)

        # --- log diffs ---
        diff_strs = [f"{d:.2f}" for d in diffs]
        log.write(f"{filename} diffs: " + ", ".join(diff_strs) + "\n")
        print(f"{filename} diffs: " + ", ".join(diff_strs))

        # clamp average shift if too large
        if abs(avg_diff) > 30:
            log.write(f"{filename}: avg_diff {avg_diff:.2f} > 30 → adjusting to 0\n")
            print(f"{filename}: avg_diff {avg_diff:.2f} > 30 → adjusting to 0")
            avg_diff = 0

        # apply brightness shift and save
        balanced = img.astype(np.float32) + avg_diff
        balanced = np.clip(balanced, 0, 255).astype(np.uint8)
        out_path = os.path.join(OUTPUT_DIR, filename)
        cv2.imwrite(out_path, balanced)

        # log the applied average shift
        log.write(f"{filename}: avg_diff={avg_diff:.2f}\n\n")
        print(f"{filename}: applied avg_diff={avg_diff:.2f}\n")

print("Done! Outputs:")
print(f"  Color‐balanced images → {OUTPUT_DIR}")
print(f"  Debug overlays        → {DEBUG_DIR}")
print(f"  Shift log            → {SHIFT_LOG}")
