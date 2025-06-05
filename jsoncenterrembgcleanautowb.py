import json
import numpy as np
import cv2 as cv
import os
from datetime import date, timedelta
from rembg import remove, new_session
from PIL import Image

def parse_ddd_to_date(year, doy):
    d = date(year,1,1) + timedelta(days=doy-1)
    return f"{d.strftime('%Y_%m_%d')}_{doy}"

def find_sms(data):
    for ln in data["readResult"]["blocks"][0]["lines"]:
        if ln["text"] in ("SMS-2","SHS-2","SHE-2","SHB-2","SMS -2","SMS-7","SHS -2","SHS-","SMS-","SMS-Z","SHS -","sns-2","SHE-Z","SHE-","THE-Z"):
            return ln["boundingPolygon"][0]
    return None

def find_ON(data):
    for ln in data["readResult"]["blocks"][0]["lines"]:
        if any(sub in ln["text"] for sub in ("ON.","OM.")):
            return ln["boundingPolygon"][0]
    return None

def fill_green_once(shifted, green_mask):
    h,w = green_mask.shape
    out = shifted.copy(); changed=False
    neigh = [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]
    ys,xs = np.where(green_mask)
    for y,x in zip(ys,xs):
        vals=[]
        for dy,dx in neigh:
            ny,nx = y+dy, x+dx
            if 0<=ny<h and 0<=nx<w and not green_mask[ny,nx]:
                vals.append(shifted[ny,nx])
        if vals:
            out[y,x] = np.mean(vals,axis=0).astype(np.uint8)
            changed=True
    return out,changed

# ───────── setup ─────────
year, start_day = 1976, 183
sat, alt = "32A","22A"
base = f"/ships22/sds/goes/digitized/{sat}/vissr/{year}"
alt_base = f"/ships22/sds/goes/digitized/{alt}/vissr/{year}"

wb = int(input("amount to add to average pixel value:"))
brush_size = int(input("brush size:"))
fourcc = cv.VideoWriter_fourcc(*'mp4v')
out = cv.VideoWriter(os.path.join(base,f"jsonshifted_cleanish_brush{brush_size}_autowb({wb})_nobg.mp4"), fourcc,10,(2000,2000))
save_folder = os.path.join(base,f"jsonshifted_cleanish_brush{brush_size}_autowb({wb})_nobg")
os.makedirs(save_folder, exist_ok=True)

upper = np.array([255,255,255],np.uint8)
kernel = cv.getStructuringElement(cv.MORPH_ELLIPSE,(brush_size,brush_size))
GREEN  = np.array((0,255,0),np.uint8)

rembg_sess = new_session("unet")

for doy in range(start_day, (366 if year%4==0 else 365)+1):
    folder = parse_ddd_to_date(year,doy)
    full = os.path.join(base,folder)
    if not os.path.isdir(full):
        altp = os.path.join(alt_base,folder)
        if os.path.isdir(altp): full=altp
        else: continue

    for fname in os.listdir(full):
        if not fname.lower().endswith(".vi.med.png"): continue
        fb = fname.replace(".vi.med.png","")
        # ── load OCR JSON and compute xshift,yshift
        meta = json.load(open(os.path.join(full,fb+".vi.json")))
        coords = find_sms(meta)
        if not coords:
            coords = find_ON(meta)
            if not coords: continue
            coords["y"] -= 14
        if not coords: continue

        xshift = (660 - int(coords["x"])) * (2000 / 757)
        yshift =  (55 - int(coords["y"])) * (2000 / 757)

        # ── read & bg‐remove
        img = cv.imread(os.path.join(full,fname))
        pil = Image.fromarray(cv.cvtColor(img,cv.COLOR_BGR2RGB))
        rembg_pil = remove(pil, session=rembg_sess).convert("RGBA")
        rgba_arr   = np.array(rembg_pil)     # H×W×4

        # ── affine shift (preserves alpha)
        T = np.float32([[1,0,xshift],[0,1,yshift]])
        shifted_rgba = cv.warpAffine(
            rgba_arr, T, (2000,2000),
            flags=cv.INTER_LINEAR,
            borderMode=cv.BORDER_CONSTANT,
            borderValue=(0,0,0,0)
        )
        shifted_bgr   = shifted_rgba[...,:3]
        shifted_alpha = shifted_rgba[...,3]

        gray = cv.cvtColor(shifted_bgr, cv.COLOR_BGR2GRAY)

        # Otsu’s threshold finds a global threshold that best separates
        # dark vs. light in this image:
        ret, _ = cv.threshold(
            gray, 0, 255,
            cv.THRESH_BINARY | cv.THRESH_OTSU
        )
        print(fb, ret)

        lw = ret + wb
        lower = np.array([lw, lw, lw], np.uint8)

        # ── green‐mask+paint
        mask = cv.inRange(shifted_bgr, lower, upper)
        mask = cv.dilate(mask, kernel)
        shifted_bgr[mask>0] = (0,255,0)

        # ── iterative fill
        green_mask = np.all(shifted_bgr==GREEN, axis=2)
        while True:
            shifted_bgr,chg = fill_green_once(shifted_bgr, green_mask)
            green_mask = np.all(shifted_bgr==GREEN, axis=2)
            if not chg or not green_mask.any(): break


        out_path = os.path.join(save_folder, fb + f".vi.med.jsonshift.brush{brush_size}.low{lw}.autowb.png")
        cv.imwrite(out_path, shifted_bgr)

        # ── composite to black & write video
        alpha_n = shifted_alpha[...,None]/255.0
        canvas  = (shifted_bgr * alpha_n).astype(np.uint8)

        out.write(canvas)

out.release()
