import cv2
import numpy as np

# 1. load your color image
img = cv2.imread("images/comb2.png")

lw = 190
# 2. build a mask of “white” pixels.
lower = np.array([lw,lw,lw], dtype=np.uint8)
upper = np.array([255,255,255], dtype=np.uint8)
mask = cv2.inRange(img, lower, upper)

# 3. dilate the mask (brush size = 11×11)
brush_size = 6
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (brush_size, brush_size))
mask_dilated = cv2.dilate(mask, kernel, iterations=1)

# 4. paint those masked pixels bright green (BGR = (0,255,0))
img[mask_dilated > 0] = (0, 255, 0)

# 5. save result
cv2.imwrite(f"images/comb2recolored_brush{brush_size}low{lw}.png", img)