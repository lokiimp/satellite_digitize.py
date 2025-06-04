import cv2
import numpy as np
import glob
import os

# ───────────────────────────────────────────────────────────────────────────────
#                          U S E R   CONFIGURATION
# ───────────────────────────────────────────────────────────────────────────────

INPUT_FOLDER    = "input_frames/"          # Folder of raw satellite PNGs
GRID_PATH       = "images/mask1px4.png"  # Transparent grid RGBA
BRIGHT_THRESH   = 180                      # Threshold to isolate grid pixels
MAX_ANGLE       = 4                        # ± degrees to search for rotation
ANGLE_STEP      = 0.1                      # Step size in degrees
MAX_SHIFT       = 200                      # ± pixels to allow for translation
INPAINT_RADIUS  = 6                        # (Unused—now using recursive fill)
RECENTER_DISK   = False                    # Whether to recenter Earth disk
SAVE_DEBUG      = True                     # Whether to save intermediate debug images
SAVE_DEBUG_FULL = False                    # save rotation images
thickness = 1                              # How much to dialte mask

OUTPUT_FOLDER   = f"1px{thickness}{INPAINT_RADIUS}/output_frames/"
DEBUG_FOLDER    = f"1px{thickness}{INPAINT_RADIUS}/debug/"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
if SAVE_DEBUG:
    os.makedirs(DEBUG_FOLDER, exist_ok=True)
# ───────────────────────────────────────────────────────────────────────────────


def load_grid_mask(path):
    """
    Loads grid.png (RGBA). Wherever alpha > 0, mask=255; else 0.
    """
    rgba = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if rgba is None:
        raise FileNotFoundError(f"Could not load '{path}'")
    if rgba.shape[2] == 4:
        alpha = rgba[:, :, 3]
        grid_mask = np.where(alpha > 0, 255, 0).astype(np.uint8)
    else:
        gray = cv2.cvtColor(rgba, cv2.COLOR_BGR2GRAY)
        _, grid_mask = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
    return grid_mask


def threshold_satellite(img_bgr, thresh, crop_top_frac=1/12):
    """
    Convert to grayscale and threshold > thresh → 255, else 0.
    Then crop off the top crop_top_frac of rows before returning.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY)
    h = binary.shape[0]
    y_offset = int(h * crop_top_frac)
    return binary[y_offset:, :], y_offset


def rotate_image(img, angle_deg, interp=cv2.INTER_LINEAR):
    h, w = img.shape[:2]
    center = (w / 2.0, h / 2.0)
    M = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=interp)


def translate_image(img, dx, dy, interp=cv2.INTER_LINEAR):
    h, w = img.shape[:2]
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(img, M, (w, h), flags=interp)


def phase_correlation_shift(src_bin, dst_bin):
    (dx, dy), _ = cv2.phaseCorrelate(src_bin.astype(np.float32), dst_bin.astype(np.float32))
    return dx, dy


def find_earth_center(img_bgr):
    h, w = img_bgr.shape[:2]
    fallback = (w // 2, h // 2)

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    _, thresh_inv = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY_INV)
    cnts, _ = cv2.findContours(thresh_inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return fallback

    big = max(cnts, key=lambda c: cv2.contourArea(c))
    M = cv2.moments(big)
    if abs(M["m00"]) < 1e-5:
        return fallback
    cx = int(M["m10"] / M["m00"])
    cy = int(M["m01"] / M["m00"])
    return (cx, cy)


def clamp_shift(dx, dy, max_shift):
    """
    Clamp dx, dy to ±max_shift.
    """
    dx_clamped = max(-max_shift, min(max_shift, dx))
    dy_clamped = max(-max_shift, min(max_shift, dy))
    return dx_clamped, dy_clamped


def match_grid_to_satellite(sat_thresh_full, grid_mask, frame_name):
    """
    For each θ in [−MAX_ANGLE..+MAX_ANGLE], rotate grid_mask by +θ,
    compute phase‐correlation shift to sat_thresh, clamp to ±MAX_SHIFT,
    translate rot_mask by (dx,dy), then measure overlap on cropped region.
    Returns (best_theta, best_dx, best_dy, best_score).
    """
    best_score = -1
    best_params = (0.0, 0.0, 0.0)

    # sat_thresh_full is already cropped top 1/12
    sat_f = sat_thresh_full.astype(np.float32)

    if SAVE_DEBUG:
        debug_subdir = os.path.join(DEBUG_FOLDER, frame_name)
        os.makedirs(debug_subdir, exist_ok=True)
        cv2.imwrite(os.path.join(debug_subdir, "sat_thresh_cropped.png"), sat_thresh_full)

    for theta in np.arange(-MAX_ANGLE, MAX_ANGLE + 1e-5, ANGLE_STEP):
        # Rotate grid mask by +θ
        rot_mask = rotate_image(grid_mask, theta, interp=cv2.INTER_NEAREST)

        # Crop off top 1/12 rows of rot_mask to match sat_thresh_full
        h, w = rot_mask.shape
        y_off = int(h / 12)
        rot_mask_cropped = rot_mask[y_off:, :]

        # Phase correlation to find unconstrained dx,dy
        dx, dy = phase_correlation_shift(rot_mask_cropped.astype(np.float32), sat_f)

        # Clamp to ±MAX_SHIFT
        dx, dy = clamp_shift(dx, dy, MAX_SHIFT)

        # Translate rot_mask by (dx,dy)
        aligned_mask = translate_image(rot_mask, dx, dy, interp=cv2.INTER_NEAREST)

        if SAVE_DEBUG_FULL:
            cv2.imwrite(os.path.join(debug_subdir, f"rot_mask_{theta:+05.2f}.png"), rot_mask)
            fn2 = f"aligned_mask_{theta:+05.2f}_dx{dx:+07.2f}_dy{dy:+07.2f}.png"
            cv2.imwrite(os.path.join(debug_subdir, fn2), aligned_mask)

        # Crop aligned_mask the same way
        aligned_mask_cropped = aligned_mask[y_off:, :]

        # Compute overlap
        overlap = cv2.countNonZero(cv2.bitwise_and(aligned_mask_cropped, sat_thresh_full))
        if overlap > best_score:
            best_score = overlap
            best_params = (theta, dx, dy)

    return (*best_params, best_score)


# ======================================================
# Recursive “green‐fill” inpainting (old method)
# ======================================================
GREEN = np.array((0, 255, 0), dtype=np.uint8)

def fill_green_once(img, green_mask):
    h, w = green_mask.shape
    out = img.copy()
    changed = False

    # 8‐neighbour offsets
    neigh = [(-1, 0), (+1, 0), (0, -1), (0, +1), (-1, -1), (-1, +1), (+1, -1), (+1, +1)]

    ys, xs = np.where(green_mask)
    for (y, x) in zip(ys, xs):
        vals = []
        for dy, dx in neigh:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w:
                if not green_mask[ny, nx]:
                    vals.append(img[ny, nx])
        if vals:
            avg = np.mean(vals, axis=0).astype(np.uint8)
            out[y, x] = avg
            changed = True

    return out, changed

def recursive_green_fill(img):
    """
    Iteratively replace pure GREEN pixels with the average of neighbouring non‐green pixels
    until no pure‐green remains or no change occurs.
    """
    while True:
        green_mask = np.all(img == GREEN, axis=2)
        if not green_mask.any():
            break
        img, changed = fill_green_once(img, green_mask)
        if not changed:
            break
    return img


# ======================================================
# Main alignment + recursive fill pipeline
# ======================================================
def align_and_fill_frame(path, grid_mask):
    frame_name = os.path.splitext(os.path.basename(path))[0]
    sat_img = cv2.imread(path)
    if sat_img is None:
        raise RuntimeError(f"Could not load '{path}'")
    h, w = sat_img.shape[:2]

    # Step 1: threshold & crop top 1/12
    sat_thresh_full, y_offset = threshold_satellite(sat_img, BRIGHT_THRESH, crop_top_frac=1/12)

    # Step 2: find best (θ, dx, dy)
    theta, dx, dy, score = match_grid_to_satellite(sat_thresh_full, grid_mask, frame_name)

    # Step 3: align the satellite by undoing translate(+dx,+dy) and rotate(+theta)
    translated_sat = translate_image(sat_img, -dx, -dy, interp=cv2.INTER_LINEAR)
    aligned_sat    = rotate_image(translated_sat, -theta, interp=cv2.INTER_LINEAR)

    # Step 4: optionally recenter the disk
    tx, ty = 0.0, 0.0
    if RECENTER_DISK:
        rot_sat_for_center = rotate_image(sat_img, -theta, interp=cv2.INTER_LINEAR)
        cx, cy = find_earth_center(rot_sat_for_center)
        tx = (w / 2.0) - cx
        ty = (h / 2.0) - cy
        aligned_sat = translate_image(aligned_sat, tx, ty, interp=cv2.INTER_LINEAR)

    # Debug: save aligned (pre‐fill)
    if SAVE_DEBUG:
        debug_subdir = os.path.join(DEBUG_FOLDER, frame_name)
        os.makedirs(debug_subdir, exist_ok=True)
        cv2.imwrite(os.path.join(debug_subdir, "aligned_sat.png"), aligned_sat)

    # Step 5: mark grid pixels (from upright grid_mask) as GREEN
    # grid_mask is 255 where grid exists. After aligning_sat, grid pixels
    # in aligned_sat coincide exactly with grid_mask positions.
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (thickness, thickness))
    thick_mask = cv2.dilate(grid_mask, kernel, iterations=1)

    marked = aligned_sat.copy()
    marked[thick_mask > 0] = GREEN  # paint grid pixels green

    # Debug: save the “green‐marked” image
    if SAVE_DEBUG:
        cv2.imwrite(os.path.join(debug_subdir, "green_marked.png"), marked)

    # Step 6: run recursive green‐fill inpainting
    final_img = recursive_green_fill(marked)

    return final_img, (theta, dx, dy, tx, ty, score)


def main():
    grid_mask = load_grid_mask(GRID_PATH)
    mh, mw = grid_mask.shape[:2]

    sat_paths = sorted(glob.glob(os.path.join(INPUT_FOLDER, "*.png")))
    if not sat_paths:
        print(f"No PNG files found in '{INPUT_FOLDER}'.")
        return

    for path in sat_paths:
        name = os.path.basename(path)
        frame_name = os.path.splitext(name)[0]
        print(f"\n▶ Processing '{name}' …")

        tmp = cv2.imread(path)
        if tmp is None:
            print(f"  ✗ Could not load '{name}'. Skipping.")
            continue
        h, w = tmp.shape[:2]
        if (h, w) != (mh, mw):
            print(f"  ✗ Size mismatch: frame {w}×{h}, grid {mw}×{mh}. Skipping.")
            continue

        try:
            final_img, params = align_and_fill_frame(path, grid_mask)
        except Exception as e:
            print(f"  ✗ Error on '{name}': {e}")
            continue

        theta, dx, dy, tx, ty, score = params
        out_name = f"{frame_name}_aligned_filled.png"
        out_path = os.path.join(OUTPUT_FOLDER, out_name)
        cv2.imwrite(out_path, final_img)

        print(f"  ✓ Saved → '{out_name}'")
        print(f"    • best angle      = {theta:.2f}°")
        print(f"    • best shift      = dx {dx:.2f}, dy {dy:.2f} (clamped to ±{MAX_SHIFT})")
        if RECENTER_DISK:
            print(f"    • recenter shift  = tx {tx:.2f}, ty {ty:.2f}")
        print(f"    • mask‐overlap    = {int(score)} pixels")

    print("\n✅ Done. Check:")
    print(f"    • Aligned & filled: {OUTPUT_FOLDER}")
    if SAVE_DEBUG:
        print(f"    • Debug images:    {DEBUG_FOLDER}")


if __name__ == "__main__":
    main()
