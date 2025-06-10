import os
import re
import cv2
import numpy as np
from datetime import date, timedelta

# --- Configuration ---
DIR = "/ships22/sds/goes/digitized"
YEAR = 1977
START_DAY = 1
MAIN_SAT = "32A"
ALT_SAT = "22A"

# Base debug directory
BASE_DEBUG = os.path.join(
    DIR,
    f"{MAIN_SAT}/vissr/{YEAR}/grid_aligned/aligned_output1px_vi/debug"
)

# Grid masks for different subpoints
GRID_MASK_FILES = {
    "5N": os.path.join(DIR, "masks/mask.5N.png"),
    "0N": os.path.join(DIR, "masks/mask.0N.png"),
    "5S": os.path.join(DIR, "masks/mask.5S.png"),
}

INPAINT_RADIUS = 7
DILATE_PIXELS = 5

OUTPUT_ROOT = os.path.join(
    DIR,
    f"{MAIN_SAT}/vissr/{YEAR}/grid_aligned/aligned_output_vi"
)
VIDEO_PATH = os.path.join(OUTPUT_ROOT, f"{YEAR}_nobg_telea_{INPAINT_RADIUS}_{DILATE_PIXELS}.mp4")
FOLDER_TELEA = os.path.join(OUTPUT_ROOT, f"telea_inpainted")

FRAME_SIZE = (2000, 2000)
FPS = 10
FOURCC = cv2.VideoWriter_fourcc(*"mp4v")

BRIGHT_THRESH = 180
MAX_ANGLE = 2.2
ANGLE_STEP = 0.1
MAX_SHIFT = 200

os.makedirs(FOLDER_TELEA, exist_ok=True)

# --- Helper functions ---

def load_mask(path):
    rgba = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if rgba is None:
        raise FileNotFoundError(f"Could not load grid mask at '{path}'")
    if rgba.shape[2] == 4:
        alpha = rgba[:, :, 3]
        mask = np.where(alpha > 0, 255, 0).astype(np.uint8)
    else:
        gray = cv2.cvtColor(rgba, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (DILATE_PIXELS, DILATE_PIXELS))
    return cv2.dilate(mask, k, iterations=1)

def threshold_satellite(img_bgr, thresh, crop_top_frac=1/12):
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY)
    h = binary.shape[0]
    y_off = int(h * crop_top_frac)
    return binary[y_off:, :], y_off

def rotate_image(img, angle, interp=cv2.INTER_LINEAR):
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w/2.0, h/2.0), angle, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=interp)

def translate_image(img, dx, dy, interp=cv2.INTER_LINEAR):
    h, w = img.shape[:2]
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(img, M, (w, h), flags=interp)

def phase_correlation_shift(src, dst):
    (dx, dy), _ = cv2.phaseCorrelate(src.astype(np.float32), dst.astype(np.float32))
    return dx, dy

def clamp_shift(dx, dy, max_shift):
    dx_c = max(-max_shift, min(max_shift, dx))
    dy_c = max(-max_shift, min(max_shift, dy))
    return dx_c, dy_c

def alignment_score(img_bgr, grid_mask):
    sat_thresh, y_off = threshold_satellite(img_bgr, BRIGHT_THRESH, crop_top_frac=1/12)
    sat_f = sat_thresh.astype(np.float32)
    best = -1
    for theta in np.arange(-MAX_ANGLE, MAX_ANGLE + 1e-5, ANGLE_STEP):
        rot = rotate_image(grid_mask, theta, interp=cv2.INTER_NEAREST)
        crop = rot[y_off:, :]
        dx, dy = phase_correlation_shift(crop.astype(np.float32), sat_f)
        dx, dy = clamp_shift(dx, dy, MAX_SHIFT)
        aligned = translate_image(rot, dx, dy, interp=cv2.INTER_NEAREST)
        aligned_crop = aligned[y_off:, :]
        overlap = cv2.countNonZero(cv2.bitwise_and(aligned_crop, sat_thresh))
        if overlap > best:
            best = overlap
    return best

def read_subpoint(json_path):
    try:
        text = open(json_path, 'r', errors='ignore').read().upper()
    except Exception:
        return None
    for key in ("5N", "0N", "5S"):
        if key in text:
            return key
    return None

def doy_folder(year, doy):
    return (date(year, 1, 1) + timedelta(days=doy-1)).strftime("%Y_%m_%d") + f"_{doy:03d}"

# Preload masks
GRID_MASKS = {k: load_mask(p) for k, p in GRID_MASK_FILES.items()}

# Map DOY to debug folder
doy_to_folder = {}
for folder_name in os.listdir(BASE_DEBUG):
    parts = folder_name.split(".")
    if len(parts) < 3:
        continue
    sat, y, d = parts[0], parts[1], parts[2]
    if sat not in (MAIN_SAT, ALT_SAT) or y != str(YEAR):
        continue
    try:
        doy = int(d)
    except ValueError:
        continue
    if doy < START_DAY:
        continue
    if doy not in doy_to_folder or (sat == MAIN_SAT and doy_to_folder[doy].startswith(ALT_SAT)):
        doy_to_folder[doy] = folder_name

last_doy = 366 if YEAR % 4 == 0 else 365
video_out = cv2.VideoWriter(VIDEO_PATH, FOURCC, FPS, FRAME_SIZE)
if not video_out.isOpened():
    raise RuntimeError(f"Failed to open video writer at '{VIDEO_PATH}'")

for doy in range(START_DAY, last_doy + 1):
    if doy not in doy_to_folder:
        continue
    basefn = doy_to_folder[doy]
    debug_dir = os.path.join(BASE_DEBUG, basefn)
    aligned_path = os.path.join(debug_dir, "aligned_nobg_with_grid.png")
    if not os.path.isfile(aligned_path):
        continue

    # Determine JSON path
    sat, year_str, doy_str = basefn.split(".")[:3]
    folder = doy_folder(int(year_str), int(doy_str))
    json_path = os.path.join(DIR, sat, "vissr", year_str, folder, basefn + ".vi.json")
    img_raw_path = os.path.join(DIR, sat, "vissr", year_str, folder, basefn + ".vi.med.png")

    sub = read_subpoint(json_path)
    if sub is None:
        print(f"Subpoint not found in {json_path}; trying all masks...")
        raw_bgr = cv2.imread(img_raw_path)
        if raw_bgr is None:
            print(f"  Missing raw image {img_raw_path}; skipping")
            continue
        scores = {k: alignment_score(raw_bgr, m) for k, m in GRID_MASKS.items()}
        sub = max(scores, key=scores.get)
    mask = GRID_MASKS[sub]

    img = cv2.imread(aligned_path)
    if img is None:
        print(f"Warning: could not load '{aligned_path}'")
        continue

    h, w = img.shape[:2]
    if (w, h) != FRAME_SIZE:
        img = cv2.resize(img, FRAME_SIZE)

    result = cv2.inpaint(img, mask, INPAINT_RADIUS, flags=cv2.INPAINT_TELEA)

    out_file = f"{basefn}.png"
    out_path = os.path.join(FOLDER_TELEA, out_file)
    cv2.imwrite(out_path, result)
    video_out.write(result)

    print(f"Processed {aligned_path} using mask {sub} → {out_path}")

video_out.release()
print(f"Done! Video saved to: {VIDEO_PATH}")
