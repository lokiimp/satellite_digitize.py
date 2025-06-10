import os
import cv2
import glob
import numpy as np
from skimage.restoration import inpaint_biharmonic
from pyinpaint import Inpaint


# ───────────────────────────────────────────────────────────────────────────────
#                          U S E R   CONFIGURATION
# ───────────────────────────────────────────────────────────────────────────────


INPUT_FOLDER    = ".5N/"             # Folder of raw satellite PNGs
GRID_PATH       = "images/grid.5N.png"        # Transparent grid RGBA
BRIGHT_THRESH   = 180                         # Threshold to isolate grid pixels
MAX_ANGLE       = 4                           # ± degrees to search for rotation
ANGLE_STEP      = 0.1                         # Step size in degrees
MAX_SHIFT       = 200                         # ± pixels to allow for translation
INPAINT_RADIUS  = 7                           # Radius for Telea/NS inpainting
RECENTER_DISK   = False                       # Whether to recenter Earth disk
SAVE_DEBUG      = True                       # Whether to save intermediate debug images
SAVE_FULL_DEBUG = False                       # Save every θ‐rotated mask image
THICKEN_PIXELS  = 5                           # How much to dilate the mask for inpainting

OUTPUT_FOLDER   = f"1pxheal.5N{THICKEN_PIXELS}{INPAINT_RADIUS}/output_frames/"
DEBUG_FOLDER    = f"1pxheal.5N{THICKEN_PIXELS}{INPAINT_RADIUS}/debug2.2/"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
if SAVE_DEBUG:
    os.makedirs(DEBUG_FOLDER, exist_ok=True)
# ───────────────────────────────────────────────────────────────────────────────


def load_grid_mask(path):
    """
    Loads grid.png (RGBA). Wherever alpha > 0, mask = 255; else 0.
    """
    rgba = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if rgba is None:
        raise FileNotFoundError(f"Could not load '{path}'")
    if rgba.shape[2] == 4:
        alpha = rgba[:, :, 3]
        mask = np.where(alpha > 0, 255, 0).astype(np.uint8)
    else:
        gray = cv2.cvtColor(rgba, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
    return mask


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
    Brute‐force θ ∈ [−MAX_ANGLE..+MAX_ANGLE] (step=ANGLE_STEP):
      1. rot_mask = rotate(grid_mask, θ)
      2. Crop top 1/12 of rot_mask → rot_crop
      3. Compute (dx,dy) = phase_correlation(rot_crop, sat_thresh_full)
      4. Clamp (dx,dy) to ±MAX_SHIFT
      5. aligned_mask = translate(rot_mask, dx, dy)
      6. Crop aligned_mask same → aligned_crop
      7. Overlap = countNonZero(aligned_crop & sat_thresh_full)
    Return best (θ, dx, dy, score). Save debug if requested.
    """
    best_score = -1
    best_params = (0.0, 0.0, 0.0)
    sat_f = sat_thresh_full.astype(np.float32)

    if SAVE_DEBUG:
        dbg_dir = os.path.join(DEBUG_FOLDER, frame_name)
        os.makedirs(dbg_dir, exist_ok=True)
        cv2.imwrite(os.path.join(dbg_dir, "sat_thresh_cropped.png"), sat_thresh_full)

    for theta in np.arange(-MAX_ANGLE, MAX_ANGLE + 1e-5, ANGLE_STEP):
        rot_mask = rotate_image(grid_mask, theta, interp=cv2.INTER_NEAREST)
        h, w = rot_mask.shape
        y_off = int(h / 12)
        rot_crop = rot_mask[y_off:, :]

        dx, dy = phase_correlation_shift(rot_crop.astype(np.float32), sat_f)
        dx, dy = clamp_shift(dx, dy, MAX_SHIFT)

        aligned_mask = translate_image(rot_mask, dx, dy, interp=cv2.INTER_NEAREST)

        if SAVE_FULL_DEBUG:
            cv2.imwrite(os.path.join(dbg_dir, f"rot_mask_{theta:+06.2f}.png"), rot_mask)
            fn2 = f"aligned_mask_{theta:+06.2f}_dx{dx:+07.2f}_dy{dy:+07.2f}.png"
            cv2.imwrite(os.path.join(dbg_dir, fn2), aligned_mask)

        aligned_crop = aligned_mask[y_off:, :]
        overlap = cv2.countNonZero(cv2.bitwise_and(aligned_crop, sat_thresh_full))
        if overlap > best_score:
            best_score = overlap
            best_params = (theta, dx, dy)

    return (*best_params, best_score)


# ───────────────────────────────────────────────────────────────────────────────
#                       Inpainting Methods (1–4)
# ───────────────────────────────────────────────────────────────────────────────
from pyinpaint import Inpaint

def inpaint_telea(image_bgr, mask):
    """OpenCV Telea inpainting."""
    return cv2.inpaint(image_bgr, mask, INPAINT_RADIUS, flags=cv2.INPAINT_TELEA)

def inpaint_ns(image_bgr, mask):
    """OpenCV Navier–Stokes inpainting."""
    return cv2.inpaint(image_bgr, mask, INPAINT_RADIUS, flags=cv2.INPAINT_NS)


def inpaint_biharmonic_color(image_bgr, mask):
    """
    scikit-image biharmonic inpainting on each channel separately.
    `mask` is a single-channel 0/255 uint8 array; we convert to boolean.
    """
    mask_bool = (mask > 0)
    # Convert BGR→RGB float in [0,1]
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    out = np.zeros_like(image_rgb)
    for c in range(3):
        # NOTE: no `multichannel` argument
        out[:, :, c] = inpaint_biharmonic(image_rgb[:, :, c], mask_bool)
    # Convert back to BGR uint8
    out_bgr = (np.clip(out * 255.0, 0, 255)).astype(np.uint8)
    out_bgr = cv2.cvtColor(out_bgr, cv2.COLOR_RGB2BGR)
    return out_bgr

def inpaint_shiftmap(image_bgr, mask):
    """
    Exemplar‐based inpainting via OpenCV‐contrib’s xphoto ShiftMap.
    Signature: cv2.xphoto.inpaint(src, mask, dst, flags)
    Returns None if ShiftMap is unavailable or fails.
    """
    try:
        dst = np.zeros_like(image_bgr)
        result = cv2.xphoto.inpaint(image_bgr, mask, dst, cv2.xphoto.INPAINT_SHIFTMAP)
        # If result is all zeros (i.e. empty), treat as failure:
        if result is None or result.size == 0:
            return None
        return result
    except Exception:
        return None

def inpaint_pyinpaint(image_bgr, mask):
    inpainted_image = Inpaint(image_bgr, mask)
    return inpainted_image()
# ───────────────────────────────────────────────────────────────────────────────
#                 Main alignment + inpainting pipeline
# ───────────────────────────────────────────────────────────────────────────────

def align_and_inpaint(image_path, grid_mask):
    """
    1. Load satellite frame.
    2. Threshold + crop top 1/12 → sat_thresh, y_off.
    3. Find best (θ, dx, dy) aligning grid_mask to sat_thresh.
    4. Align original BGR by translate(−dx,−dy)+rotate(−θ).
    5. Optionally recenter Earth disk → aligned.
    6. Build thickened mask = dilate(grid_mask, THICKEN_PIXELS × THICKEN_PIXELS).
    7. Return aligned_bgr and thick_mask.
    """
    frame_name = os.path.splitext(os.path.basename(image_path))[0]
    sat_bgr = cv2.imread(image_path)
    if sat_bgr is None:
        raise FileNotFoundError(f"Cannot load '{image_path}'")
    h, w = sat_bgr.shape[:2]

    sat_thresh_full, y_off = threshold_satellite(sat_bgr, BRIGHT_THRESH, crop_top_frac=1/12)
    theta, dx, dy, score = match_grid_to_satellite(sat_thresh_full, grid_mask, frame_name)

    trans = translate_image(sat_bgr, -dx, -dy, interp=cv2.INTER_LINEAR)
    aligned = rotate_image(trans, -theta, interp=cv2.INTER_LINEAR)

    if RECENTER_DISK:
        rot_for_center = rotate_image(sat_bgr, -theta, interp=cv2.INTER_LINEAR)
        cx, cy = find_earth_center(rot_for_center)
        tx = (w / 2.0) - cx
        ty = (h / 2.0) - cy
        aligned = translate_image(aligned, tx, ty, interp=cv2.INTER_LINEAR)

    # Dilate grid_mask to produce a “thick” mask for inpainting
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (THICKEN_PIXELS, THICKEN_PIXELS))
    thick_mask = cv2.dilate(grid_mask, kernel, iterations=1)

    return aligned, thick_mask, (theta, dx, dy, score)


def main():
    grid_mask = load_grid_mask(GRID_PATH)
    mh, mw = grid_mask.shape

    sat_paths = sorted(glob.glob(os.path.join(INPUT_FOLDER, "*.png")))
    if not sat_paths:
        print(f"No PNGs found in '{INPUT_FOLDER}'.")
        return

    for path in sat_paths:
        frame_name = os.path.splitext(os.path.basename(path))[0]
        print(f"\n▶ Processing '{frame_name}' …")

        try:
            aligned_bgr, mask_for_inpaint, params = align_and_inpaint(path, grid_mask)
        except Exception as e:
            print(f"  ✗ Failed on '{frame_name}': {e}")
            continue

        theta, dx, dy, score = params

        # Create per-image output folder
        img_out_folder = os.path.join(OUTPUT_FOLDER, frame_name)
        os.makedirs(img_out_folder, exist_ok=True)

        # 1) Save aligned with grid (just the aligned BGR)
        cv2.imwrite(os.path.join(img_out_folder, "aligned_with_grid.png"), aligned_bgr)

        # 2) Telea inpainting
        telea = inpaint_telea(aligned_bgr, mask_for_inpaint)
        cv2.imwrite(os.path.join(img_out_folder, "inpaint_telea.png"), telea)

        # 3) Navier–Stokes inpainting
        ns = inpaint_ns(aligned_bgr, mask_for_inpaint)
        cv2.imwrite(os.path.join(img_out_folder, "inpaint_ns.png"), ns)

        # 4) Biharmonic inpainting (scikit‐image)
        biharm = inpaint_biharmonic_color(aligned_bgr, mask_for_inpaint)
        cv2.imwrite(os.path.join(img_out_folder, "inpaint_biharmonic.png"), biharm)

        # 5) ShiftMap inpainting (opencv‐contrib)
        # 5) ShiftMap inpainting (opencv‐contrib)
        shiftmap = inpaint_shiftmap(aligned_bgr, mask_for_inpaint)
        if shiftmap is not None:
            cv2.imwrite(os.path.join(img_out_folder, "inpaint_shiftmap.png"), shiftmap)
        else:
            print("  – ShiftMap inpainting unavailable or failed for", frame_name)

        # (Optional) Save debug images
        if SAVE_DEBUG:
            dbg = os.path.join(DEBUG_FOLDER, frame_name)
            os.makedirs(dbg, exist_ok=True)
            cv2.imwrite(os.path.join(dbg, "aligned.png"), aligned_bgr)
            cv2.imwrite(os.path.join(dbg, "mask_for_inpaint.png"), mask_for_inpaint)

        print(f"  ✓ Saved outputs for '{frame_name}'. θ={theta:.2f}°, dx={dx:.1f}, dy={dy:.1f}, score={int(score)}")

    print("\nAll done. Check folders under:", OUTPUT_FOLDER)


if __name__ == "__main__":
    main()
