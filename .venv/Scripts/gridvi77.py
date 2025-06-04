import os
import cv2
import json
import glob
import numpy as np
from datetime import date, timedelta
from rembg import remove, new_session
from PIL import Image

# ───────────────────────────────────────────────────────────────────────────────
#                          U S E R   CONFIGURATION
# ───────────────────────────────────────────────────────────────────────────────

# Folders and paths
YEAR           = 1977
START_DAY      = 1
mask_filename = "mask1px4.png"
INPUT_BASE     = "/ships22/sds/goes/digitized/"  # base directory for satellite data
OUTPUT_ROOT    = os.path.join(INPUT_BASE, f"32A/vissr/{year}/grid_aligned/aligned_output1px_vi/")   # root for all outputs
GRID_PATH      = os.path.join(INPUT_BASE, f"masks/{mask_filename}") # transparent‐RGBA grid mask

# Alignment parameters
BRIGHT_THRESH  = 180     # threshold to isolate grid pixels
MAX_ANGLE      = 2.2       # ±° to search when aligning grid
ANGLE_STEP     = 0.1     # θ step in degrees
MAX_SHIFT      = 200     # ± pixels to allow translation

# Green‐fill parameters
THICKEN_PIXELS = 3       # dilate grid mask by this thickness
GREEN          = np.array((0, 255, 0), dtype=np.uint8)

# Background removal
USE_REMBG      = True    # remove background before alignment
REMBG_SESSION  = new_session("unet")

# Dates & Sat info
MAIN_SAT       = "32A"   # primary satellite code
ALT_SAT        = "22A"   # alternate if primary folder missing

# Video parameters
FRAME_SIZE     = (2000, 2000)
FPS            = 10
FOURCC         = cv2.VideoWriter_fourcc(*'mp4v')

# Flags
RECENTER_DISK  = False   # recenter Earth disk after alignment
SAVE_DEBUG     = True    # save per‐frame debug images
SAVE_FULL_DEBUG= False   # save every θ‐rotated mask image

# ───────────────────────────────────────────────────────────────────────────────

# Create output sub‐folders
os.makedirs(OUTPUT_ROOT, exist_ok=True)
OS_FOLDERS = {
    "video_no_bg_with_grid":      os.path.join(OUTPUT_ROOT, "vid_nobg_with_grid.mp4"),
    "video_no_bg_inpainted":      os.path.join(OUTPUT_ROOT, "vid_nobg_inpainted.mp4"),
    "folder_aligned_with_grid":   os.path.join(OUTPUT_ROOT, "aligned_with_grid/"),
    "folder_aligned_green":       os.path.join(OUTPUT_ROOT, "aligned_green_grid/"),
    "folder_aligned_no_grid":     os.path.join(OUTPUT_ROOT, "aligned_no_grid/"),
    "folder_aligned_no_grid_bg":  os.path.join(OUTPUT_ROOT, "aligned_no_grid_nobg/"),
    "debug":                      os.path.join(OUTPUT_ROOT, "debug/"),
}
for k, p in OS_FOLDERS.items():
    if k.startswith("folder"):
        os.makedirs(p, exist_ok=True)
    elif k == "debug" and SAVE_DEBUG:
        os.makedirs(p, exist_ok=True)

# Initialize video writers
vid_no_bg_with_grid = cv2.VideoWriter(OS_FOLDERS["video_no_bg_with_grid"], FOURCC, FPS, FRAME_SIZE)
vid_no_bg_inpainted = cv2.VideoWriter(OS_FOLDERS["video_no_bg_inpainted"], FOURCC, FPS, FRAME_SIZE)

# ───────────────────────────────────────────────────────────────────────────────
#                       Helper functions for alignment & inpainting
# ───────────────────────────────────────────────────────────────────────────────

def load_grid_mask(path):
    """
    Loads a transparent RGBA grid (white lines on alpha=0). Returns single‐channel 0/255 mask.
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
    Converts BGR→GRAY, thresholds > thresh → 255. Crops off top crop_top_frac of rows.
    Returns (binary_cropped, y_offset).
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY)
    h = binary.shape[0]
    y_off = int(h * crop_top_frac)
    return binary[y_off:, :], y_off

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

def clamp_shift(dx, dy, max_shift):
    dx_c = max(-max_shift, min(max_shift, dx))
    dy_c = max(-max_shift, min(max_shift, dy))
    return dx_c, dy_c

def find_earth_center(img_bgr):
    h, w = img_bgr.shape[:2]
    fallback = (w//2, h//2)
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    _, inv = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY_INV)
    cnts, _ = cv2.findContours(inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return fallback
    big = max(cnts, key=lambda c: cv2.contourArea(c))
    M = cv2.moments(big)
    if abs(M["m00"]) < 1e-5:
        return fallback
    cx = int(M["m10"] / M["m00"])
    cy = int(M["m01"] / M["m00"])
    return (cx, cy)

def match_grid_to_satellite(sat_thresh, grid_mask, frame_name, y_off):
    """
    Brute‐force θ ∈ [−MAX_ANGLE..+MAX_ANGLE] (step ANGLE_STEP):
      • rot_mask = rotate(grid_mask, +θ)
      • rot_mask_crop = rot_mask[y_off:, :]
      • compute (dx,dy) = phase_correlation(rot_mask_crop, sat_thresh)
      • clamp (dx,dy) to ±MAX_SHIFT
      • aligned_mask = translate(rot_mask, dx, dy)
      • aligned_mask_crop = aligned_mask[y_off:, :]
      • overlap = countNonZero(aligned_mask_crop & sat_thresh)
    Return best (θ, dx, dy, score).
    Saves per‐θ debug if SAVE_FULL_DEBUG/ SAVE_DEBUG=True.
    """
    best_score = -1
    best_params = (0.0, 0.0, 0.0)
    sat_f = sat_thresh.astype(np.float32)
    if SAVE_DEBUG:
        dbg_dir = os.path.join(OS_FOLDERS["debug"], frame_name)
        os.makedirs(dbg_dir, exist_ok=True)
        cv2.imwrite(os.path.join(dbg_dir, "sat_thresh_cropped.png"), sat_thresh)

    for theta in np.arange(-MAX_ANGLE, MAX_ANGLE + 1e-5, ANGLE_STEP):
        rot_mask = rotate_image(grid_mask, theta, interp=cv2.INTER_NEAREST)
        # Crop same top-off
        h, w = rot_mask.shape
        crop_mask = rot_mask[y_off:, :]

        dx, dy = phase_correlation_shift(crop_mask.astype(np.float32), sat_f)
        dx, dy = clamp_shift(dx, dy, MAX_SHIFT)
        aligned_mask = translate_image(rot_mask, dx, dy, interp=cv2.INTER_NEAREST)

        if SAVE_FULL_DEBUG:
            cv2.imwrite(os.path.join(dbg_dir, f"rot_mask_{theta:+05.2f}.png"), rot_mask)
            fn2 = f"aligned_mask_{theta:+05.2f}_dx{dx:+07.2f}_dy{dy:+07.2f}.png"
            cv2.imwrite(os.path.join(dbg_dir, fn2), aligned_mask)

        aligned_crop = aligned_mask[y_off:, :]
        overlap = cv2.countNonZero(cv2.bitwise_and(aligned_crop, sat_thresh))
        if overlap > best_score:
            best_score = overlap
            best_params = (theta, dx, dy)

    return (*best_params, best_score)

def fill_green_once(img, green_mask):
    h, w = green_mask.shape
    out = img.copy()
    changed = False
    neigh = [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]
    ys, xs = np.where(green_mask)
    for y, x in zip(ys, xs):
        vals = []
        for dy, dx in neigh:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not green_mask[ny, nx]:
                vals.append(img[ny, nx])
        if vals:
            out[y, x] = np.mean(vals, axis=0).astype(np.uint8)
            changed = True
    return out, changed

def recursive_green_fill(img):
    while True:
        green_mask = np.all(img == GREEN, axis=2)
        if not green_mask.any(): break
        img, chg = fill_green_once(img, green_mask)
        if not chg: break
    return img

# ───────────────────────────────────────────────────────────────────────────────
#                 Main pipeline: alignment + outputs creation
# ───────────────────────────────────────────────────────────────────────────────

# Load grid mask once
grid_mask = load_grid_mask(GRID_PATH)
mh, mw = grid_mask.shape

# Helper to remove background via rembg (returns RGBA numpy)
def remove_background(img_bgr):
    pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    rem = remove(pil, session=REMBG_SESSION).convert("RGBA")
    return np.array(rem)

# Process all dates
for doy in range(START_DAY, (366 if YEAR % 4 == 0 else 365) + 1):
    folder = (date(YEAR, 1, 1) + timedelta(days=doy-1)).strftime("%Y_%m_%d") + f"_{doy:03d}"
    main_dir = os.path.join(INPUT_BASE, MAIN_SAT, "vissr", str(YEAR), folder)
    if not os.path.isdir(main_dir):
        alt_dir = os.path.join(INPUT_BASE, ALT_SAT, "vissr", str(YEAR), folder)
        if os.path.isdir(alt_dir):
            main_dir = alt_dir
        else:
            continue

    for fname in sorted(os.listdir(main_dir)):
        if not fname.lower().endswith(".vi.med.png"):
            continue
        basefn = fname.replace(".vi.med.png", "")
        json_path = os.path.join(main_dir, basefn + ".vi.json")
        img_path  = os.path.join(main_dir, fname)
        if not os.path.isfile(json_path): continue

        # ── Load JSON (we no longer use SMS‐based shift; skip)
        # If desired, parse JSON for metadata; but alignment uses grid.

        # ── Read satellite frame
        sat_bgr = cv2.imread(img_path)
        if sat_bgr is None: continue

        # ── Remove background if requested
        if USE_REMBG:
            rgba = remove_background(sat_bgr)
            alpha_ch = rgba[..., 3]
            sat_rgb_nobg = cv2.cvtColor(rgba, cv2.COLOR_RGBA2RGB)
        else:
            sat_rgb_nobg = sat_bgr.copy()
            alpha_ch = np.full((sat_bgr.shape[0], sat_bgr.shape[1]), 255, dtype=np.uint8)

        # ── Align to grid
        sat_thresh_full, y_off = threshold_satellite(sat_rgb_nobg, BRIGHT_THRESH, crop_top_frac=1/12)
        theta, dx, dy, score = match_grid_to_satellite(sat_thresh_full, grid_mask, basefn, y_off)

        # ─— Apply inverse transform to original BGR and BG‐removed
        sat_trans_bgr = translate_image(sat_bgr, -dx, -dy, interp=cv2.INTER_LINEAR)
        aligned_bgr   = rotate_image(sat_trans_bgr, -theta, interp=cv2.INTER_LINEAR)

        sat_trans_nobg = translate_image(sat_rgb_nobg, -dx, -dy, interp=cv2.INTER_LINEAR)
        aligned_nobg   = rotate_image(sat_trans_nobg, -theta, interp=cv2.INTER_LINEAR)

        # If recentering:
        if RECENTER_DISK:
            rot_for_center = rotate_image(sat_bgr, -theta, interp=cv2.INTER_LINEAR)
            cx, cy = find_earth_center(rot_for_center)
            tx = (mw/2.0) - cx
            ty = (mh/2.0) - cy
            aligned_bgr  = translate_image(aligned_bgr,  tx,  ty, interp=cv2.INTER_LINEAR)
            aligned_nobg = translate_image(aligned_nobg, tx,  ty, interp=cv2.INTER_LINEAR)

        # ── “With gridlines” = just the aligned BGR (grid was overlaid originally)
        out_with_grid_path = os.path.join(OS_FOLDERS["folder_aligned_with_grid"], basefn + ".png")
        cv2.imwrite(out_with_grid_path, aligned_bgr)

        # For “no background, with gridlines” video:
        frame_nobg = aligned_nobg
        vid_no_bg_with_grid.write(frame_nobg)

        # ── Create “green‐marked” version
        # First thicken grid_mask, then mark those pixels green on aligned_bgr
        kernel_t = cv2.getStructuringElement(cv2.MORPH_RECT, (THICKEN_PIXELS, THICKEN_PIXELS))
        thick_mask = cv2.dilate(grid_mask, kernel_t, iterations=1)
        aligned_green = aligned_bgr.copy()
        aligned_green[thick_mask > 0] = GREEN
        out_green_path = os.path.join(OS_FOLDERS["folder_aligned_green"], basefn + ".png")
        cv2.imwrite(out_green_path, aligned_green)

        # ── Create “no gridlines” = recursive‐green‐fill on aligned_green
        filled = recursive_green_fill(aligned_green.copy())
        out_no_grid_path = os.path.join(OS_FOLDERS["folder_aligned_no_grid"], basefn + ".png")
        cv2.imwrite(out_no_grid_path, filled)

        # ── For “no background, inpainted” video: apply green‐fill to aligned_nobg
        aligned_nobg_green = aligned_nobg.copy()
        aligned_nobg_green[thick_mask > 0] = GREEN
        nobg_filled = recursive_green_fill(aligned_nobg_green.copy())
        vid_no_bg_inpainted.write(nobg_filled)

        # ── Save “no grid, no background” frame
        out_no_grid_nobg = os.path.join(OS_FOLDERS["folder_aligned_no_grid_bg"], basefn + ".png")
        cv2.imwrite(out_no_grid_nobg, nobg_filled)

        # ── Debug: save aligned BGR, aligned_nobg, green_marked, threshold, etc.
        if SAVE_DEBUG:
            dbg_dir = os.path.join(OS_FOLDERS["debug"], basefn)
            os.makedirs(dbg_dir, exist_ok=True)
            cv2.imwrite(os.path.join(dbg_dir, "aligned_with_grid.png"), aligned_bgr)
            cv2.imwrite(os.path.join(dbg_dir, "aligned_nobg_with_grid.png"), aligned_nobg)
            cv2.imwrite(os.path.join(dbg_dir, "aligned_green.png"), aligned_green)
            cv2.imwrite(os.path.join(dbg_dir, "aligned_nobg_green.png"), aligned_nobg_green)
            cv2.imwrite(os.path.join(dbg_dir, "filled.png"), filled)
            cv2.imwrite(os.path.join(dbg_dir, "nobg_filled.png"), nobg_filled)
            # Save the thresholded satellite crop
            cv2.imwrite(os.path.join(dbg_dir, "sat_thresh_cropped.png"), sat_thresh_full)

        print(f"Processed {basefn}: θ={theta:.2f}°, dx={dx:.2f}, dy={dy:.2f}, score={int(score)}")

# Release video writers
vid_no_bg_with_grid.release()
vid_no_bg_inpainted.release()

print("\nAll done. Outputs written to:", OUTPUT_ROOT)
