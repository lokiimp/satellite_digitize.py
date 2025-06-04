import json
import numpy as np
import cv2 as cv
import os
from datetime import date, timedelta
from rembg import remove, new_session
from PIL import Image

img = cv.imread("images/comb.png")


xshift = 0
yshift = 0


brush_size = 6

upper = np.array([255,255,255],np.uint8)
kernel = cv.getStructuringElement(cv.MORPH_ELLIPSE,(brush_size,brush_size))
GREEN  = np.array((0,255,0),np.uint8)

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
pil = Image.fromarray(cv.cvtColor(img, cv.COLOR_BGR2RGB))
rembg_pil = remove(pil).convert("RGBA")
rgba_arr = np.array(rembg_pil)  # H×W×4



# ── affine shift (preserves alpha)
T = np.float32([[1, 0, xshift], [0, 1, yshift]])
shifted_rgba = cv.warpAffine(
    rgba_arr, T, (2000, 2000),
    flags=cv.INTER_LINEAR,
    borderMode=cv.BORDER_CONSTANT,
    borderValue=(0, 0, 0, 0)
)
shifted_bgr = shifted_rgba[..., :3]
shifted_alpha = shifted_rgba[..., 3]


gray = cv.cvtColor(shifted_bgr, cv.COLOR_BGR2GRAY)

# Otsu’s threshold finds a global threshold that best separates
# dark vs. light in this image:
ret, _ = cv.threshold(
    gray, 0, 255,
    cv.THRESH_BINARY | cv.THRESH_OTSU
)
print(ret)

lw = ret + 135
lower = np.array([lw,lw,lw],np.uint8)


# ── green‐mask+paint
mask = cv.inRange(shifted_bgr, lower, upper)
mask = cv.dilate(mask, kernel)
shifted_bgr[mask > 0] = (0, 255, 0)

#cv.imwrite(f"images/ack", shifted_bgr)

# ── iterative fill
green_mask = np.all(shifted_bgr == GREEN, axis=2)
while True:
    shifted_bgr, chg = fill_green_once(shifted_bgr, green_mask)
    green_mask = np.all(shifted_bgr == GREEN, axis=2)
    if not chg or not green_mask.any(): break

out_path = f"images/comb.autowb.vi.med.jsonshift.brush{brush_size}.low{lw}.png"
cv.imwrite(out_path, shifted_bgr)