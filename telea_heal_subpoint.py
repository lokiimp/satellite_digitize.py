import os
import re
import cv2
import numpy as np
from datetime import date, timedelta
from rembg import remove, new_session
from PIL import Image
import sys

class Tee:
    def __init__(self, filename):
        self.file = open(filename, "w", encoding="utf-8")
        self.stdout = sys.stdout

    def write(self, data):
        self.file.write(data)
        self.stdout.write(data)

    def flush(self):
        self.file.flush()
        self.stdout.flush()

# --- Configuration ---
DIR = "/ships22/sds/goes/digitized"
YEAR = 1978
START_DAY = 1
MAIN_SAT = "33A"
ALT_SAT = "22A"
ALT_SAT2 = ""

# Grid masks for different subpoints
GRID_MASK_FILES = {
    "5N": os.path.join(DIR, "masks/mask0.5N135.0W2.png"),
    "0N": os.path.join(DIR, "masks/mask0.0N135.0W.png"),
    "5S": os.path.join(DIR, "masks/mask0.5S135.0W.png"),
}

INPAINT_RADIUS = 6
DILATE_PIXELS = 5

OUTPUT_ROOT = os.path.join(
    DIR,
    f"{MAIN_SAT}/vissr/{YEAR}/grid_aligned/aligned_output_ir"
)
os.makedirs(OUTPUT_ROOT, exist_ok=True)
OUTPUT_LOG = os.path.join(OUTPUT_ROOT, "output.txt")
sys.stdout = Tee(OUTPUT_LOG)
OS_FOLDERS = {
    "video_no_bg_with_grid": os.path.join(OUTPUT_ROOT, f"{YEAR}_vid_nobg_with_grid.mp4"),
    "video_no_bg_inpainted": os.path.join(
        OUTPUT_ROOT,
        f"{YEAR}_vid_nobg_telea_r{INPAINT_RADIUS}_d{DILATE_PIXELS}.mp4",
    ),
    "folder_aligned_with_grid": os.path.join(OUTPUT_ROOT, "aligned_with_grid"),
    "folder_aligned_green": os.path.join(OUTPUT_ROOT, "aligned_green_grid"),
    "folder_aligned_no_grid": os.path.join(OUTPUT_ROOT, "aligned_no_grid"),
    "folder_aligned_no_grid_bg": os.path.join(
        OUTPUT_ROOT, "aligned_no_grid_nobg"
    ),
    "debug": os.path.join(OUTPUT_ROOT, "debug"),
}

FOLDER_TELEA = OS_FOLDERS["folder_aligned_no_grid"]
DEBUG_ROOT = OS_FOLDERS["debug"]

GREEN = np.array((0, 255, 0), dtype=np.uint8)
USE_REMBG = True
REMBG_SESSION = new_session("unet")

FRAME_SIZE = (2000, 2000)
FPS = 10
FOURCC = cv2.VideoWriter_fourcc(*"mp4v")
SAVE_DEBUG = True

BRIGHT_THRESH = 180
MAX_ANGLE = 2.2
ANGLE_STEP = 0.1
MAX_SHIFT = 200

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
    return mask

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

def match_grid_to_satellite(sat_thresh, grid_mask, frame_name, y_off):
    best_score = -1
    best_params = (0.0, 0.0, 0.0)
    sat_f = sat_thresh.astype(np.float32)
    if SAVE_DEBUG:
        dbg_dir = os.path.join(DEBUG_ROOT, frame_name)
        os.makedirs(dbg_dir, exist_ok=True)
        cv2.imwrite(os.path.join(dbg_dir, "sat_thresh_cropped.png"), sat_thresh)

    for theta in np.arange(-MAX_ANGLE, MAX_ANGLE + 1e-5, ANGLE_STEP):
        rot_mask = rotate_image(grid_mask, theta, interp=cv2.INTER_NEAREST)
        crop_mask = rot_mask[y_off:, :]
        dx, dy = phase_correlation_shift(crop_mask.astype(np.float32), sat_f)
        dx, dy = clamp_shift(dx, dy, MAX_SHIFT)
        aligned_mask = translate_image(rot_mask, dx, dy, interp=cv2.INTER_NEAREST)
        aligned_crop = aligned_mask[y_off:, :]
        overlap = cv2.countNonZero(cv2.bitwise_and(aligned_crop, sat_thresh))
        if overlap > best_score:
            best_score = overlap
            best_params = (theta, dx, dy)

    return (*best_params, best_score)

def remove_background(img_bgr):
    pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    rem = remove(pil, session=REMBG_SESSION).convert("RGBA")
    return np.array(rem)

import json

def read_subpoint(json_path):
    """
    Parses the JSON at json_path, extracts only the 'text' fields, and then:
      - Returns "5N" if any text contains SN or 5N not followed by 'O'
      - Returns "0N" if any text contains ON or 0N not followed by 'O'
      - Returns "5S" if any text contains SS, 58, 38, 88, or 5S not followed by 'E'
    in that priority order.  Otherwise returns None.
    """
    # 1) Load JSON
    try:
        with open(json_path, 'r', errors='ignore') as f:
            data = json.load(f)
    except Exception:
        return None

    # 2) Gather only the captionResult.text + each OCR line.text
    texts = []
    cap = data.get("captionResult", {})
    if isinstance(cap.get("text"), str):
        texts.append(cap["text"].upper())

    for block in data.get("readResult", {}).get("blocks", []):
        for line in block.get("lines", []):
            if isinstance(line.get("text"), str):
                texts.append(line["text"].upper())

    # 3) Define regex patterns with negative look-arounds
    patterns = {
        "5N": [r"SN(?![OS])", r"5N(?!O)", r"SM(?![OS])"],  # don't match SN or 5N if followed by 'O'
        "0N": [r"(?<!M)ON(?!O)", r"0N(?!O)", r"OM(?!O)"],  # don't match ON or 0N if followed by 'O'
        "5S": [r"SS", r"58", r"38", r"88", r"55", r"59", r"5S(?!E)"]  # don't match 5S if followed by 'E'
    }

    # 4) Search in priority order
    for result, pats in patterns.items():
        for snippet in texts:
            for pat in pats:
                if re.search(pat, snippet):
                    return result

    return None



def doy_folder(year, doy):
    return (date(year, 1, 1) + timedelta(days=doy-1)).strftime("%Y_%m_%d") + f"_{doy:03d}"

# Preload masks
GRID_MASKS = {k: load_mask(p) for k, p in GRID_MASK_FILES.items()}

# Video writers and output folders
for k, p in OS_FOLDERS.items():
    if k.startswith("folder"):
        os.makedirs(p, exist_ok=True)
    elif k == "debug" and SAVE_DEBUG:
        os.makedirs(p, exist_ok=True)

vid_with_grid = cv2.VideoWriter(
    OS_FOLDERS["video_no_bg_with_grid"], FOURCC, FPS, FRAME_SIZE
)
vid_inpaint = cv2.VideoWriter(
    OS_FOLDERS["video_no_bg_inpainted"], FOURCC, FPS, FRAME_SIZE
)
if not vid_with_grid.isOpened() or not vid_inpaint.isOpened():
    raise RuntimeError("Failed to open video writers")

# Determine last day in year
last_doy = 366 if YEAR % 4 == 0 else 365

for doy in range(START_DAY, last_doy + 1):
    folder = doy_folder(YEAR, doy)
    main_dir = os.path.join(DIR, MAIN_SAT, "vissr", str(YEAR), folder)
    if not os.path.isdir(main_dir):
        alt_dir = os.path.join(DIR, ALT_SAT, "vissr", str(YEAR), folder)
        if os.path.isdir(alt_dir):
            main_dir = alt_dir
        else:
            alt_dir = os.path.join(DIR, ALT_SAT2, "vissr", str(YEAR), folder)
            if os.path.isdir(alt_dir):
                main_dir = alt_dir
            else: continue

    for fname in sorted(os.listdir(main_dir)):
        if not fname.lower().endswith(".ir.med.png"):
            continue
        basefn = fname.replace(".ir.med.png", "")
        json_path = os.path.join(main_dir, basefn + ".vi.json")
        img_path = os.path.join(main_dir, fname)
        if not os.path.isfile(json_path):
            continue

        sat_bgr = cv2.imread(img_path)
        if sat_bgr is None:
            continue

        sub = read_subpoint(json_path)
        if sub is None:
            print(f"ERROR AT {fname}, NO SUBPOINT FOUND")
            scores = {k: alignment_score(sat_bgr, m) for k, m in GRID_MASKS.items()}
            sub = max(scores, key=scores.get)
        grid_mask = GRID_MASKS[sub]

        # Background removal
        if USE_REMBG:
            rgba = remove_background(sat_bgr)
            sat_nobg = cv2.cvtColor(rgba, cv2.COLOR_RGBA2RGB)
        else:
            sat_nobg = sat_bgr.copy()

        # Align to grid
        sat_thresh, y_off = threshold_satellite(sat_nobg, BRIGHT_THRESH, crop_top_frac=1 / 12)
        theta, dx, dy, score = match_grid_to_satellite(sat_thresh, grid_mask, basefn, y_off)

        sat_trans_bgr = translate_image(sat_bgr, -dx, -dy)
        aligned_bgr = rotate_image(sat_trans_bgr, -theta)
        sat_trans_nobg = translate_image(sat_nobg, -dx, -dy)
        aligned_nobg = rotate_image(sat_trans_nobg, -theta)

        if aligned_bgr.shape[1::-1] != FRAME_SIZE:
            aligned_bgr = cv2.resize(aligned_bgr, FRAME_SIZE)
            aligned_nobg = cv2.resize(aligned_nobg, FRAME_SIZE)

        out_with_grid = os.path.join(OS_FOLDERS["folder_aligned_with_grid"], basefn + ".png")
        cv2.imwrite(out_with_grid, aligned_bgr)
        vid_with_grid.write(aligned_nobg)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (DILATE_PIXELS, DILATE_PIXELS))
        thick_mask = cv2.dilate(grid_mask, kernel, iterations=1)
        aligned_green = aligned_bgr.copy()
        aligned_green[thick_mask > 0] = (0, 255, 0)
        out_green = os.path.join(OS_FOLDERS["folder_aligned_green"], basefn + ".png")
        cv2.imwrite(out_green, aligned_green)

        telea_mask = thick_mask
        filled = cv2.inpaint(aligned_bgr, telea_mask, INPAINT_RADIUS, flags=cv2.INPAINT_TELEA)
        out_no_grid = os.path.join(OS_FOLDERS["folder_aligned_no_grid"], basefn + ".png")
        cv2.imwrite(out_no_grid, filled)

        filled_nobg = cv2.inpaint(aligned_nobg, telea_mask, INPAINT_RADIUS, flags=cv2.INPAINT_TELEA)
        vid_inpaint.write(filled_nobg)
        out_no_grid_nobg = os.path.join(OS_FOLDERS["folder_aligned_no_grid_bg"], basefn + ".png")
        cv2.imwrite(out_no_grid_nobg, filled_nobg)

        if SAVE_DEBUG:
            dbg_dir = os.path.join(DEBUG_ROOT, basefn)
            os.makedirs(dbg_dir, exist_ok=True)
            cv2.imwrite(os.path.join(dbg_dir, "aligned_with_grid.png"), aligned_bgr)
            cv2.imwrite(os.path.join(dbg_dir, "aligned_green.png"), aligned_green)
            cv2.imwrite(os.path.join(dbg_dir, "telea.png"), filled)
            cv2.imwrite(os.path.join(dbg_dir, "mask.png"), telea_mask)

        print(
            f"Processed {basefn}: θ={theta:.2f}, dx={dx:.2f}, dy={dy:.2f}, score={int(score)}, sub={sub}"
        )

vid_with_grid.release()
vid_inpaint.release()
print("\nAll done. Outputs written to:", OUTPUT_ROOT)