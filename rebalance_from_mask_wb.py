import os
import cv2
import numpy as np
import glob

# ───────────────────────────────────────────────────────────────────────────────
#                        USER–CONFIGURATION
# ───────────────────────────────────────────────────────────────────────────────
INPUT_DIR      = "/ships22/sds/goes/digitized/32A/vissr/1978/grid_aligned/aligned_output_vi_4/aligned_with_grid"
MASK_PATH      = "/ships22/sds/goes/digitized/masks/maskbar.png"
OUTPUT_DIR     = "/ships22/sds/goes/digitized/32A/vissr/1978/grid_aligned/aligned_output_vi_4/aligned_with_grid_color_and_whitebalanced_3"
DEBUG_BAR_DIR  = "/ships22/sds/goes/digitized/32A/vissr/1978/grid_aligned/aligned_output_vi_4/aligned_with_grid_debug_bar_7"
#DEBUG_MASK_DIR = "/ships22/sds/goes/digitized/32A/vissr/1978/grid_aligned/aligned_output_vi_4/aligned_with_grid_debug_mask_overlay_6"

for d in (OUTPUT_DIR, DEBUG_BAR_DIR):
    os.makedirs(d, exist_ok=True)

SHIFT_LOG      = os.path.join(OUTPUT_DIR, "shift_log.txt")
N_SAMPLES      = 17
BRIGHT_THRESH  = 170    # threshold to isolate bar pixels
ANGLE_RANGE    = 2      # ± degrees for coarse search
COARSE_STEP    = .5    # degrees
FINE_RANGE     = .5    # ± around best coarse angle for fine search
FINE_STEP      = 0.1    # degrees
SHIFT_CLAMP    = 200    # max translation clamp
VERT_OFFSET    = 50     # pixels above median mask line to sample
HORIZ_START_OFS= 50    # pixels to shift start right
HORIZ_END_OFS  = 30     # pixels to shift end left

# Load and binarize bar mask
rgba = cv2.imread(MASK_PATH, cv2.IMREAD_UNCHANGED)
if rgba is None:
    raise FileNotFoundError(f"Mask bar not found at {MASK_PATH}")
if rgba.shape[2] == 4:
    alpha = rgba[:, :, 3]
    bar_mask = (alpha > 0).astype(np.uint8) * 255
else:
    gray_tmp = cv2.cvtColor(rgba, cv2.COLOR_BGR2GRAY)
    _, bar_mask = cv2.threshold(gray_tmp, 1, 255, cv2.THRESH_BINARY)

# threshold to binary
def threshold_bin(gray, thresh):
    _, b = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY)
    return b

# clamp shift
def clamp(dx, dy, m=SHIFT_CLAMP):
    return max(-m, min(m, dx)), max(-m, min(m, dy))

# coarse-to-fine alignment in ROI (top 1/12)
def find_bar_transform(img_bin, mask):
    h, w = mask.shape
    roi_h = h // 12
    img_roi = img_bin[:roi_h, :].astype(np.float32)
    best = {'score': -1, 'angle': 0, 'dx': 0, 'dy': 0}

    def scan(angles):
        nonlocal best
        for ang in angles:
            Mrot = cv2.getRotationMatrix2D((w/2, h/2), ang, 1.0)
            mask_rot = cv2.warpAffine(mask, Mrot, (w, h), flags=cv2.INTER_NEAREST)
            crop = mask_rot[:roi_h, :].astype(np.float32)
            (dx, dy), _ = cv2.phaseCorrelate(crop, img_roi)
            dx, dy = clamp(dx, dy)
            Mtrans = np.float32([[1, 0, dx], [0, 1, dy]])
            aligned = cv2.warpAffine(mask_rot, Mtrans, (w, h), flags=cv2.INTER_NEAREST)
            overlap = cv2.countNonZero(cv2.bitwise_and(aligned[:roi_h, :], img_bin[:roi_h, :]))
            if overlap > best['score']:
                best.update({'score': overlap, 'angle': ang, 'dx': dx, 'dy': dy})

    scan(np.arange(-ANGLE_RANGE, ANGLE_RANGE + 1e-6, COARSE_STEP))
    lo = best['angle'] - FINE_RANGE
    hi = best['angle'] + FINE_RANGE
    scan(np.arange(lo, hi + 1e-6, FINE_STEP))
    return best

# main processing
def main():
    with open(SHIFT_LOG, 'w') as log:
        for img_path in sorted(glob.glob(os.path.join(INPUT_DIR, '*.png'))):
            fname = os.path.basename(img_path)
            img = cv2.imread(img_path)
            if img is None:
                log.write(f"{fname}: load failed\n")
                continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            img_bin = threshold_bin(gray, BRIGHT_THRESH)
            tf = find_bar_transform(img_bin, bar_mask)

            # align mask
            h, w = bar_mask.shape
            Mrot = cv2.getRotationMatrix2D((w/2, h/2), tf['angle'], 1.0)
            mask_rot = cv2.warpAffine(bar_mask, Mrot, (w, h), flags=cv2.INTER_NEAREST)
            Mtrans = np.float32([[1, 0, tf['dx']], [0, 1, tf['dy']]])
            mask_aligned = cv2.warpAffine(mask_rot, Mtrans, (w, h), flags=cv2.INTER_NEAREST)

            ys, xs = np.where(mask_aligned > 0)
            if len(ys) == 0:
                log.write(f"{fname}: bar not found\n")
                continue
            # median mask line
            y_line = int(np.median(ys))
            # sample line offset above
            y_sample = max(y_line - VERT_OFFSET, 0)
            # horizontal offsets
            x_min, x_max = xs.min() + HORIZ_START_OFS, xs.max() - HORIZ_END_OFS
            x_min = max(0, x_min)
            x_max = min(w-1, x_max)

            # sample positions
            seglen = (x_max - x_min) / N_SAMPLES
            sample_x = (x_min + (np.arange(N_SAMPLES) + 0.5) * seglen).astype(int)
            vals = gray[y_sample, sample_x].astype(float)
            tgt = np.linspace(0, 255, N_SAMPLES)
            diffs = tgt - vals
            diffs[np.abs(diffs) > 65] = 0
            avg_shift = diffs.mean()

            # debug bar overlay at sample line
            dbg_bar = img.copy()
            cv2.line(dbg_bar, (x_min, y_sample), (x_max, y_sample), (0, 255, 0), 2)
            for x in sample_x:
                cv2.circle(dbg_bar, (x, y_sample), 5, (0, 255, 0), -1)
            cv2.imwrite(os.path.join(DEBUG_BAR_DIR, fname), dbg_bar)

            # debug mask overlay (green mask on image)
            # dbg_mask = img.copy()
            # green_mask = np.zeros_like(img)
            # green_mask[mask_aligned > 0] = (0, 255, 0)
            # overlay = cv2.addWeighted(dbg_mask, 0.7, green_mask, 0.3, 0)
            # cv2.imwrite(os.path.join(DEBUG_MASK_DIR, fname), overlay)

            # apply brightness shift
            out = np.clip(img.astype(np.float32) + avg_shift, 0, 255).astype(np.uint8)

            # white-balance rightmost sample point
            # sample original color at last point
            wb_x = sample_x[-3]
            h_img, w_img = img.shape[:2]
            wb_y = min(y_sample + 50, h_img - 1)
            # sample original color at that location
            bx, gx, rx = img[wb_y, wb_x]
            # compute per-channel gains to map sample to pure white (255)
            gb = 255.0 / bx if bx > 0 else 1.0
            gg = 255.0 / gx if gx > 0 else 1.0
            gr = 255.0 / rx if rx > 0 else 1.0
            
            wb = np.empty_like(out, dtype=np.float32)
            wb[..., 0] = out[..., 0].astype(np.float32) * gb
            wb[..., 1] = out[..., 1].astype(np.float32) * gg
            wb[..., 2] = out[..., 2].astype(np.float32) * gr
            wb = np.clip(wb, 0, 255).astype(np.uint8)

            # save final
            cv2.imwrite(os.path.join(OUTPUT_DIR, fname), wb)
            log.write(f"{fname}: angle={tf['angle']:.2f}, dx={tf['dx']:.1f}, dy={tf['dy']:.1f}, shift={avg_shift:.2f}, wb_gains=({gb:.2f},{gg:.2f},{gr:.2f})\n")
            print(f"{fname}: applied shift {avg_shift:.2f}, white-balance gains=(" +
                  f"{gb:.2f},{gg:.2f},{gr:.2f})")

if __name__ == '__main__':
    main()
