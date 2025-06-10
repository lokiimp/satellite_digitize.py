import cv2
import numpy as np

# 1. load your color image
date = "ats3.19720228.1724.00"
img = cv2.imread(f"images/{date}.png")

lw = 190
brush_size = 8


# 2. build a mask of “white” pixels.
lower = np.array([lw,lw,lw], dtype=np.uint8)
upper = np.array([255,255,255], dtype=np.uint8)
mask = cv2.inRange(img, lower, upper)

# 3. dilate the mask

kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (brush_size, brush_size))
mask_dilated = cv2.dilate(mask, kernel, iterations=1)

# 4. paint those masked pixels bright green (BGR = (0,255,0))
img[mask_dilated > 0] = (0, 255, 0)

# the “green” we painted (B, G, R)
GREEN = np.array((0,255,0), dtype=np.uint8)

# a function that, given the image and green‐mask, does one pass:
def fill_green_once(img, green_mask):
    h, w = green_mask.shape
    # prepare a new image to write into
    out = img.copy()
    changed = False

    # offsets for 8-neighbours
    neigh = [(-1,0),(+1,0),(0,-1),(0,+1),(-1,-1),(-1,+1),(1,-1),(1,1)]

    # get coords of all green pixels
    ys, xs = np.where(green_mask)
    for (y, x) in zip(ys, xs):
        vals = []
        for dy, dx in neigh:
            ny, nx = y+dy, x+dx
            if 0 <= ny < h and 0 <= nx < w:
                if not green_mask[ny, nx]:
                    vals.append(img[ny, nx])
        if vals:
            # compute mean of neighbours (axis=0 over [B,G,R])
            avg = np.mean(vals, axis=0).astype(np.uint8)
            out[y, x] = avg
            changed = True

    return out, changed

# build initial mask of exactly green pixels
mask = np.all(img == GREEN, axis=2)

# iterate until mask is empty or no progress
while True:
    img, changed = fill_green_once(img, mask)
    # rebuild mask
    mask = np.all(img == GREEN, axis=2)
    if not changed or not mask.any():
        break

cv2.imwrite(f"images/{date}final_inpaintedbrush{brush_size}low{lw}.png", img)
