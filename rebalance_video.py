import os
import glob
import cv2

# ───────────────────────────────────────────────────────────────────────────────
#                        U S E R–CONFIGURATION
# ───────────────────────────────────────────────────────────────────────────────

# Folder containing your color‐balanced PNGs named like 32A.1976.183.204500.png
INPUT_DIR     = "/ships22/sds/goes/digitized/32A/vissr/1978/grid_aligned/aligned_output_vi_4/aligned_with_grid_color_and_whitebalanced_3"

# Output video path
OUTPUT_VIDEO  = os.path.join(INPUT_DIR, "1978_grid_wb_rebalanced.mp4")

# Video settings
FPS           = 10
FOURCC        = cv2.VideoWriter_fourcc(*"mp4v")  # MPEG‐4

# ───────────────────────────────────────────────────────────────────────────────

# Gather all PNGs, parse DOY and time, sort by (DOY, time)
entries = []
for path in glob.glob(os.path.join(INPUT_DIR, "*.png")):
    fname = os.path.basename(path)
    parts = fname.split(".")
    # Expect ["32A","1976","183","204500","png"]
    if len(parts) < 4:
        continue
    try:
        doy  = int(parts[2])
        t_ms = int(parts[3])
    except ValueError:
        continue
    entries.append((doy, t_ms, path))

# sort by day‐of‐year, then by time
entries.sort(key=lambda x: (x[0], x[1]))

if not entries:
    raise RuntimeError(f"No PNG files found in {INPUT_DIR}")

# Read first image to get frame size
first_img = cv2.imread(entries[0][2])
if first_img is None:
    raise RuntimeError(f"Failed to load {entries[0][2]}")
h, w = first_img.shape[:2]
frame_size = (w, h)

# Initialize VideoWriter
writer = cv2.VideoWriter(OUTPUT_VIDEO, FOURCC, FPS, frame_size)
if not writer.isOpened():
    raise RuntimeError(f"Could not open video writer for {OUTPUT_VIDEO}")

# Write each frame in sorted order
for doy, t_ms, path in entries:
    img = cv2.imread(path)
    if img is None:
        print(f"Warning: could not load {path}, skipping")
        continue
    # Resize if necessary
    if (img.shape[1], img.shape[0]) != frame_size:
        img = cv2.resize(img, frame_size)
    writer.write(img)
    print(f"Added DOY {doy}, time {t_ms} → {os.path.basename(path)}")

writer.release()
print(f"Done! Video saved to: {OUTPUT_VIDEO}")