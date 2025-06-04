import json
import numpy as np
import cv2 as cv
import os
from datetime import date, timedelta

def parse_ddd_to_date(year, doy):
    try:
        d = date(year, 1, 1) + timedelta(days=doy - 1)
        return f"{d.strftime('%Y_%m_%d')}_{doy}"
    except ValueError:
        return None


def find_sms(data):
    for ln in data["readResult"]["blocks"][0]["lines"]:
        if ln["text"] in ("SMS-2","SHS-2","SHE-2","SHB-2","SMS -2","SMS-7","SHS -2","SHS-","SMS-","SMS-Z","SHS -","sns-2","SHE-Z","SHE-","THE-Z"):
            return ln["boundingPolygon"][0]
    return None


def find_ON(data):
    for ln in data["readResult"]["blocks"][0]["lines"]:
        if any(sub in ln["text"] for sub in ("ON.", "OM.")):
            return ln["boundingPolygon"][0]
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
fourcc = cv.VideoWriter_fourcc(*'mp4v')
save_path = os.path.join(base, "med_1976_shift_vi_full_cleanish_auto_white.mp4")
out = cv.VideoWriter(save_path, fourcc, 10, (2000, 2000))
save_folder = os.path.join(base,"shifted_cleanish_auto_white")
os.makedirs(save_folder, exist_ok=True)


brush_size = 5
kernel = cv.getStructuringElement(cv.MORPH_ELLIPSE, (brush_size, brush_size))
GREEN = np.array((0, 255, 0), dtype=np.uint8)

# Determine days in year
is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
max_day = 366 if is_leap else 365

missing_count = 0

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
            json_file = file_base + ".vi.json"
            with open(os.path.join(full_path, json_file), 'r') as json_file_obj:
                data = json.load(json_file_obj)

            coords = find_sms(data)
            if coords is None:
                coords = find_ON(data)
                if coords is None:
                    print(f"No SMS-2 or ON block in {json_file}")
                    continue
                coords["y"] = int(coords["y"]) - 14

            xshift = 660 - int(coords["x"])
            yshift = 55 - int(coords["y"])
            #print(full_path,xshift, yshift)
            img_path = os.path.join(full_path, file)
            img = cv.imread(img_path)
            if img is None:
                print(f"Failed to load image {img_path}")
                continue

            height, width = img.shape[:2]
            shift_height, shift_width = yshift * (height / 757), xshift * (width / 757)
            T = np.float32([[1, 0, shift_width], [0, 1, shift_height]])
            shifted = cv.warpAffine(img, T, (width, height))

            x_ref, y_ref = 1575, 25  # ← change to the pixel that’s always on the line

            # sample a small patch around that point to be robust
            patch = shifted[y_ref - 2:y_ref + 3, x_ref - 2:x_ref + 3]  # a 5×5 neighborhood
            gray_patch = cv.cvtColor(patch, cv.COLOR_BGR2GRAY)
            # take the maximum (or mean) brightness in that patch
            lw = int(gray_patch.min())
            if lw < 200:
                lw = 200

            lower = np.array([lw, lw, lw], dtype=np.uint8)
            upper = np.array([255, 255, 255], dtype=np.uint8)

            mask = cv.inRange(shifted, lower, upper)

            # 3. dilate the mask
            mask_dilated = cv.dilate(mask, kernel, iterations=1)

            # 4. paint those masked pixels bright green (BGR = (0,255,0))
            shifted[mask_dilated > 0] = (0, 255, 0)


            # build initial mask of exactly green pixels
            mask = np.all(shifted == GREEN, axis=2)

            # iterate until mask is empty or no progress
            while True:
                shifted, changed = fill_green_once(shifted, mask)
                # rebuild mask
                mask = np.all(shifted == GREEN, axis=2)
                if not changed or not mask.any():
                    break

            out_path = os.path.join(save_folder, file_base + f".vi.med.shift.brush{brush_size}.lowauto({lw}).png")
            cv.imwrite(out_path, shifted)


            out.write(shifted)
out.release()

