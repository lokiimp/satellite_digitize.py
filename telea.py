import cv2
import numpy as np

# 1. load your color image
date = "ats3.19720228.1724.00"
img = cv2.imread(f"images/{date}.png")

lw = 180
brush_size = 5
inpaint_radius = 7

# 2. build a mask of “white” pixels.
lower = np.array([lw,lw,lw], dtype=np.uint8)
upper = np.array([255,255,255], dtype=np.uint8)
mask = cv2.inRange(img, lower, upper)

# 3. dilate the mask

kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (brush_size, brush_size))
mask_dilated = cv2.dilate(mask, kernel, iterations=1)

telea_result = cv2.inpaint(img, mask_dilated, inpaint_radius, flags=cv2.INPAINT_TELEA)


cv2.imwrite(f"images/{date}telea_inpaintedbrush{brush_size}low{lw}.png", telea_result)
