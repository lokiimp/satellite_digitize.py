import json
import numpy as np
import cv2 as cv
import os
from datetime import date, timedelta
from rembg import remove, new_session
from PIL import Image


def parse_ddd_to_date(year, doy):
    try:
        d = date(year, 1, 1) + timedelta(days=doy - 1)
        return f"{d.strftime('%Y_%m_%d')}_{doy}"
    except ValueError:
        return None



# a function that, given the image and green‐mask, does one pass:
def fill_green_once(shifted, green_mask):
    h, w = green_mask.shape
    # prepare a new image to write into
    out = shifted.copy()
    changed = False

    # offsets for 8-neighbours
    neigh = [(-1, 0), (+1, 0), (0, -1), (0, +1), (-1, -1), (-1, +1), (1, -1), (1, 1)]

    # get coords of all green pixels
    ys, xs = np.where(green_mask)
    for (y, x) in zip(ys, xs):
        vals = []
        for dy, dx in neigh:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w:
                if not green_mask[ny, nx]:
                    vals.append(shifted[ny, nx])
        if vals:
            # compute mean of neighbours (axis=0 over [B,G,R])
            avg = np.mean(vals, axis=0).astype(np.uint8)
            out[y, x] = avg
            changed = True

    return out, changed


year = 1976
start_day = 183
satellite = "32A"
alt_satellite = "22A"

base = os.path.join(
    "/ships22/sds/goes/digitized",
    satellite,
    "vissr",
    str(year)
)
alt_base  = os.path.join(
    "/ships22/sds/goes/digitized",
    alt_satellite,
    "vissr",
    str(year)
)
lw = int(input("low:"))
brush_size = int(input("brush size:"))
fourcc = cv.VideoWriter_fourcc(*'mp4v')

save_path = os.path.join(base, f"med_1976_cent_vi_full_cleanish_brush{brush_size}_lw{lw}_1shift.mp4")
out = cv.VideoWriter(save_path, fourcc, 10, (2000, 2000))

save_folder = os.path.join(base,f"shifted_cleanish_brush{brush_size}_lw{lw}_1shift")
unclean_save_folder = os.path.join(base,f"shifted_off_nobg_1shift")
os.makedirs(save_folder, exist_ok=True)
os.makedirs(unclean_save_folder, exist_ok=True)

model_name = "unet"
rembg_session = new_session(model_name)


lower = np.array([lw, lw, lw], dtype=np.uint8)
upper = np.array([255, 255, 255], dtype=np.uint8)
kernel = cv.getStructuringElement(cv.MORPH_ELLIPSE, (brush_size, brush_size))
GREEN = np.array((0, 255, 0), dtype=np.uint8)

# Determine days in year
is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
max_day = 366 if is_leap else 365

for doy in range(start_day, max_day + 1):
    folder = parse_ddd_to_date(year, doy)
    if folder is None:
        continue

    full_path = os.path.join(base, folder)
    if not os.path.isdir(full_path):
        alt_path = os.path.join(alt_base, folder)
        if os.path.isdir(alt_path):
            full_path = alt_path
            print(f"Falling back to {alt_path}")
        else:
            print(f"Missing directory for both {satellite} and {alt_satellite}: {folder}")
            continue


    for file in os.listdir(full_path):
        if file.lower().endswith(".vi.med.png"):
            file_base = file.replace(".vi.med.png","")


            img_path = os.path.join(full_path, file)
            img = cv.imread(img_path)
            if img is None:
                print(f"Failed to load image {img_path}")
                continue

            pil = Image.fromarray(cv.cvtColor(img, cv.COLOR_BGR2RGB))
            rembg_pil = remove(pil, session=rembg_session).convert("RGBA")

            rgba_arr = np.array(rembg_pil)  # shape = (H, W, 4)
            bgr = rgba_arr[:, :, :3]  # just the color channels

            alpha = rgba_arr[:, :, 3]  # shape = (H, W)
            widths = (alpha > 0).sum(axis=1)  # count of non-transparent pixels per row
            y_max = int(np.argmax(widths))
            xs = np.where(alpha[y_max] > 0)[0]
            runs = []
            start = xs[0]
            prev = xs[0]
            for x in xs[1:]:
                if x == prev + 1:
                    prev = x
                else:
                    runs.append((start, prev))
                    start = prev = x
            runs.append((start, prev))
            x_start = x_end = None
            for a, b in runs:
                if (b - a + 1) >= 10:
                    x_start, x_end = a, b
                    break
            if x_start is None:
                # fallback: just use the full span
                x_start, x_end = int(xs.min()), int(xs.max())
            x_center = (x_start + x_end) // 2



            xshift = 1000 - x_center
            yshift = 1050 - y_max

            height, width = img.shape[:2]
            T = np.float32([[1, 0, xshift], [0, 1, yshift]])
            shifted_rgba = cv.warpAffine(rgba_arr, T, (width, height),
                                         flags=cv.INTER_LINEAR,
                                         borderMode=cv.BORDER_CONSTANT,
                                         borderValue=(0, 0, 0, 0))
            shifted_bgr = shifted_rgba[..., :3]
            shifted_alpha = shifted_rgba[..., 3]

            unclean_out_path = os.path.join(unclean_save_folder, file_base + f".vi.med.shiftoffnobg.png")
            cv.imwrite(unclean_out_path, shifted_rgba)


            # 2. build a mask of “white” pixels.
            mask = cv.inRange(shifted_bgr, lower, upper)

            # 3. dilate the mask
            mask_dilated = cv.dilate(mask, kernel, iterations=1)

            # 4. paint those masked pixels bright green (BGR = (0,255,0))
            shifted_bgr[mask_dilated > 0] = (0, 255, 0)


            # build initial mask of exactly green pixels
            mask = np.all(shifted_bgr == GREEN, axis=2)

            # iterate until mask is empty or no progress
            while True:
                shifted_bgr, changed = fill_green_once(shifted_bgr, mask)
                # rebuild mask
                mask = np.all(shifted_bgr == GREEN, axis=2)
                if not changed or not mask.any():
                    break

            out_path = os.path.join(save_folder, file_base + f".vi.med.shift.brush{brush_size}.low{lw}.1shift.png")
            cv.imwrite(out_path, shifted_bgr)

            alpha_norm = shifted_rgba[:, :, 3:] / 255.0
            canvas = (shifted_bgr * alpha_norm).astype(np.uint8)
            out.write(canvas)
out.release()
