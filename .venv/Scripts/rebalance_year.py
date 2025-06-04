import json
import numpy as np
import cv2 as cv
import os
from datetime import date, timedelta
from rembg import remove, new_session
from PIL import Image

def parse_ddd_to_date(year, doy):
    d = date(year, 1, 1) + timedelta(days=doy - 1)
    return f"{d.strftime('%Y_%m_%d')}_{doy:03d}"

def find_sms(data):
    for ln in data["readResult"]["blocks"][0]["lines"]:
        if ln["text"] in ("SMS-2","SHS-2","SHE-2","SHB-2","SMS -2","SMS-7",
                          "SHS -2","SHS-","SMS-","SMS-Z","SHS -","sns-2",
                          "SHE-Z","SHE-","THE-Z"):
            return ln["boundingPolygon"][0]
    return None

def find_ON(data):
    for ln in data["readResult"]["blocks"][0]["lines"]:
        if any(sub in ln["text"] for sub in ("ON.","OM.")):
            return ln["boundingPolygon"][0]
    return None

def fill_green_once(shifted, green_mask):
    h, w = green_mask.shape
    out = shifted.copy()
    changed = False
    neigh = [(-1, 0), (1, 0), (0, -1), (0, 1),
             (-1, -1), (-1, 1), (1, -1), (1, 1)]
    ys, xs = np.where(green_mask)
    for y, x in zip(ys, xs):
        vals = []
        for dy, dx in neigh:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not green_mask[ny, nx]:
                vals.append(shifted[ny, nx])
        if vals:
            out[y, x] = np.mean(vals, axis=0).astype(np.uint8)
            changed = True
    return out, changed

def grayworld_whitebalance(img_bgr: np.ndarray) -> np.ndarray:
    img = img_bgr.astype(np.float32)
    b_mean, g_mean, r_mean = cv.mean(img)[:3]
    gray_mean = (b_mean + g_mean + r_mean) / 3.0
    b_scale = gray_mean / b_mean
    g_scale = gray_mean / g_mean
    r_scale = gray_mean / r_mean
    img[:, :, 0] = np.clip(img[:, :, 0] * b_scale, 0, 255)
    img[:, :, 1] = np.clip(img[:, :, 1] * g_scale, 0, 255)
    img[:, :, 2] = np.clip(img[:, :, 2] * r_scale, 0, 255)
    return img.astype(np.uint8)

# ───────── setup ─────────
YEAR_START = 1976
DAY_START_1976 = 183
YEAR_END   = 1977
DAY_END_1977 = 182

sat, alt = "32A", "22A"

# We’ll write the combined-output video & folder into the 1976 directory:
base_root_1976  = f"/ships22/sds/goes/digitized/{sat}/vissr/{YEAR_START}"
# NOTE: we don’t need a separate “base_root_1977” for outputs,
# but we _will_ build per‐year folders inside the loop.

wb         = int(input("amount to add to average pixel value: "))
brush_size = int(input("brush size: "))
fourcc     = cv.VideoWriter_fourcc(*"mp4v")

out_video_path = os.path.join(
    base_root_1976,
    f"jsonshifted_cleanish_brush{brush_size}_fullautowb({wb})_1976-1977_nobg.mp4"
)
out = cv.VideoWriter(out_video_path, fourcc, 10, (2000, 2000))

save_folder = os.path.join(
    base_root_1976,
    f"jsonshifted_cleanish_brush{brush_size}_fullautowb({wb})_1976-1977_nobg"
)
os.makedirs(save_folder, exist_ok=True)

upper = np.array([255, 255, 255], np.uint8)
kernel = cv.getStructuringElement(cv.MORPH_ELLIPSE, (brush_size, brush_size))
GREEN = np.array((0, 255, 0), np.uint8)

rembg_sess = new_session("unet")

# ───────── build our “year & DOY spans” ─────────
spans = [
    (YEAR_START, DAY_START_1976, 366 if YEAR_START % 4 == 0 else 365),
    (YEAR_END,   1,               DAY_END_1977)
]

for (year, doy_start, doy_end) in spans:
    base     = f"/ships22/sds/goes/digitized/{sat}/vissr/{year}"
    alt_base = f"/ships22/sds/goes/digitized/{alt}/vissr/{year}"

    for doy in range(doy_start, doy_end + 1):
        folder = parse_ddd_to_date(year, doy)
        full = os.path.join(base, folder)
        if not os.path.isdir(full):
            altp = os.path.join(alt_base, folder)
            if os.path.isdir(altp):
                full = altp
            else:
                # neither 32A nor 22A folder exists for this date → skip
                continue

        for fname in os.listdir(full):
            if not fname.lower().endswith(".vi.med.png"):
                continue

            fb = fname.replace(".vi.med.png", "")
            # ── load JSON & find centering coords
            json_path = os.path.join(full, fb + ".vi.json")
            if not os.path.isfile(json_path):
                continue
            meta = json.load(open(json_path, "r"))

            coords = find_sms(meta)
            if not coords:
                coords = find_ON(meta)
                if not coords: continue
                coords["y"] -= 14
            if not coords: continue

            # scale shifts from 757→2000
            xshift = (660 - int(coords["x"])) * (2000 / 757)
            yshift = ( 55 - int(coords["y"])) * (2000 / 757)

            # ── read original & remove background
            img = cv.imread(os.path.join(full, fname))
            if img is None:
                continue

            pil = Image.fromarray(cv.cvtColor(img, cv.COLOR_BGR2RGB))
            rembg_pil = remove(pil, session=rembg_sess).convert("RGBA")
            rgba_arr   = np.array(rembg_pil)  # shape = (2000, 2000, 4)

            # ── affine shift on RGBA (keeps transparency)
            T = np.float32([[1, 0, xshift], [0, 1, yshift]])
            shifted_rgba = cv.warpAffine(
                rgba_arr, T, (2000, 2000),
                flags=cv.INTER_LINEAR,
                borderMode=cv.BORDER_CONSTANT,
                borderValue=(0, 0, 0, 0)
            )
            shifted_bgr   = shifted_rgba[..., :3]
            shifted_alpha = shifted_rgba[..., 3]

            # ── white–balance each frame
            shifted_bgr = grayworld_whitebalance(shifted_bgr)

            # ── Otsu to find per‐image white cutoff
            gray = cv.cvtColor(shifted_bgr, cv.COLOR_BGR2GRAY)
            ret, _ = cv.threshold(
                gray, 0, 255, cv.THRESH_BINARY | cv.THRESH_OTSU
            )
            print(fb, ret)
            lw_img = int(ret) + wb
            lower = np.array([lw_img, lw_img, lw_img], np.uint8)

            # ── paint “over‐bright” pixels green
            mask = cv.inRange(shifted_bgr, lower, upper)
            mask = cv.dilate(mask, kernel, iterations=1)
            shifted_bgr[mask > 0] = (0, 255, 0)

            # ── iterative green‐fill
            green_mask = np.all(shifted_bgr == GREEN, axis=2)
            while True:
                shifted_bgr, changed = fill_green_once(shifted_bgr, green_mask)
                green_mask = np.all(shifted_bgr == GREEN, axis=2)
                if not changed or not green_mask.any():
                    break

            # ── save a PNG of this cleaned frame
            out_png = os.path.join(
                save_folder,
                fb + f".vi.med.jsonshift.brush{brush_size}.low{lw_img}.png"
            )
            cv.imwrite(out_png, shifted_bgr)

            # ── composite over black and write to MP4
            alpha_n = shifted_alpha[..., None] / 255.0
            canvas  = (shifted_bgr * alpha_n).astype(np.uint8)
            out.write(canvas)

out.release()
