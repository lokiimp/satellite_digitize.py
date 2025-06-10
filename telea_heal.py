import os
import cv2
import numpy as np

# ───────────────────────────────────────────────────────────────────────────────
#                          U S E R   CONFIGURATION
# ───────────────────────────────────────────────────────────────────────────────

DIR            = "/ships22/sds/goes/digitized"
YEAR           = 1976
START_DAY      = 183
MAIN_SAT       = "32A"
ALT_SAT        = "22A"

# Base “debug” directory containing folders like “32A.1976.184.204500”
BASE_DEBUG     = os.path.join(
    DIR,
    f"{MAIN_SAT}/vissr/{YEAR}/grid_aligned/aligned_output1px_vi/debug"
)

# Static grid mask (aligned to those images)
GRID_MASK_PATH = os.path.join(DIR, "masks/mask1px4.png")

# Inpainting parameters
INPAINT_RADIUS = 7      # radius for cv2.INPAINT_TELEA
DILATE_PIXELS  = 5      # how many pixels to dilate the mask

# Output locations
OUTPUT_ROOT    = os.path.join(
    DIR,
    f"{MAIN_SAT}/vissr/{YEAR}/grid_aligned/aligned_output1px_vi"
)
VIDEO_PATH     = os.path.join(OUTPUT_ROOT, "vid_nobg_telea_v2.mp4")
FOLDER_TELEA   = os.path.join(OUTPUT_ROOT, "telea_inpainted_v2")

# Video parameters
FRAME_SIZE     = (2000, 2000)                     # width × height
FPS            = 10
FOURCC         = cv2.VideoWriter_fourcc(*"mp4v")  # H.264

# ───────────────────────────────────────────────────────────────────────────────

# Ensure output folder exists
os.makedirs(FOLDER_TELEA, exist_ok=True)

# Load and dilate the static grid mask once
grid_rgba = cv2.imread(GRID_MASK_PATH, cv2.IMREAD_UNCHANGED)
if grid_rgba is None:
    raise FileNotFoundError(f"Could not load grid mask at '{GRID_MASK_PATH}'")

if grid_rgba.shape[2] == 4:
    alpha = grid_rgba[:, :, 3]
    grid_mask = np.where(alpha > 0, 255, 0).astype(np.uint8)
else:
    gray = cv2.cvtColor(grid_rgba, cv2.COLOR_BGR2GRAY)
    _, grid_mask = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)

kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (DILATE_PIXELS, DILATE_PIXELS))
dilated_mask = cv2.dilate(grid_mask, kernel, iterations=1)

# Build a mapping from DOY → folder name, preferring MAIN_SAT over ALT_SAT
doy_to_folder = {}
for folder_name in os.listdir(BASE_DEBUG):
    parts = folder_name.split(".")
    if len(parts) < 3:
        continue
    sat, year_str, doy_str = parts[0], parts[1], parts[2]
    if sat not in (MAIN_SAT, ALT_SAT) or year_str != str(YEAR):
        continue
    try:
        doy = int(doy_str)
    except ValueError:
        continue
    # Only consider days ≥ START_DAY
    if doy < START_DAY:
        continue
    # If not yet stored, or replace ALT with MAIN
    if doy not in doy_to_folder or (sat == MAIN_SAT and doy_to_folder[doy].startswith(ALT_SAT)):
        doy_to_folder[doy] = folder_name

# Determine last DOY of the year
last_doy = 366 if (YEAR % 4 == 0) else 365

# Prepare H.264 video writer
video_out = cv2.VideoWriter(VIDEO_PATH, FOURCC, FPS, FRAME_SIZE)
if not video_out.isOpened():
    raise RuntimeError(f"Failed to open video writer at '{VIDEO_PATH}'")

# Iterate through DOYs in order
for doy in range(START_DAY, last_doy + 1):
    if doy not in doy_to_folder:
        continue
    folder_name = doy_to_folder[doy]
    aligned_path = os.path.join(BASE_DEBUG, folder_name, "aligned_nobg_with_grid.png")
    if not os.path.isfile(aligned_path):
        continue

    # Load the already‐aligned, background‐removed, grid‐on image
    img = cv2.imread(aligned_path)
    if img is None:
        print(f"Warning: could not load '{aligned_path}'")
        continue

    h, w = img.shape[:2]
    if (w, h) != FRAME_SIZE:
        img = cv2.resize(img, FRAME_SIZE)

    # Inpaint using Telea with the dilated mask
    telea_result = cv2.inpaint(img, dilated_mask, INPAINT_RADIUS, flags=cv2.INPAINT_TELEA)

    # Save inpainted image
    out_filename = f"{folder_name}.png"
    out_path = os.path.join(FOLDER_TELEA, out_filename)
    cv2.imwrite(out_path, telea_result)

    # Write frame to video
    video_out.write(telea_result)

    print(f"Processed {aligned_path} → {out_path}")

video_out.release()
print(f"Done! Video saved to: {VIDEO_PATH}")
