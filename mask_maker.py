import cv2
import numpy as np

# 1. Load the color image (unchanged)
img = cv2.imread("images/comb.5S.png")
if img is None:
    raise FileNotFoundError("Could not load 'images/comb2.png'")

# 2. Build a mask of “white”-ish pixels (threshold = 170 here)
lw = 160
lower = np.array([lw, lw, lw], dtype=np.uint8)
upper = np.array([255, 255, 255], dtype=np.uint8)
mask = cv2.inRange(img, lower, upper)

# 3. Dilate the mask (brush size = 6×6)
brush_size = 1
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (brush_size, brush_size))
mask_dilated = cv2.dilate(mask, kernel, iterations=1)

# 4. Create a 4-channel RGBA mask image that's white where mask_dilated>0, transparent elsewhere
h, w = mask_dilated.shape
rgba_mask = np.zeros((h, w, 4), dtype=np.uint8)  # initialize all channels to 0
# Wherever mask_dilated is nonzero, set RGB to white and alpha to 255
rgba_mask[mask_dilated > 0] = (255, 255, 255, 255)

# 5. Save the white-on-transparent PNG to disk
cv2.imwrite(f"images/comb.5S_mask_trans_brush{brush_size}_low{lw}.png", rgba_mask)
