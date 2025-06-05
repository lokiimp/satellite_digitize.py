import cv2
import numpy as np

# ── 1) LOAD IMAGE (change this path to wherever you have your PNG) ──
img_path = f'images/32A.1976.183.204500.vi.med.png'
img = cv2.imread(img_path)
if img is None:
    raise RuntimeError(f"Could not load '{img_path}'.  Make sure the path is correct.")

# ── 2) CONVERT TO GRAYSCALE ──
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# ── 3) THRESHOLD TO ISOLATE BRIGHT GRID LINES ──
#    Any pixel > 180 (out of 255) becomes pure white in thresh.
#    You can push this up (200–220) if you see too many non–grid whites,
#    or pull it down (160–180) if some grid lines remain undetected.
_, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)

# ── 4) “CLOSE” GAPS IN DASHED LINES ──
#    (MORPH_CLOSE will join very small gaps so that our long‐kernel open can pick up dashed segments.)
kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel_close, iterations=1)

# ── 5) EXTRACT HORIZONTAL LINES ──
#    Use a very “flat” kernel—e.g. (width=80 px, height=1 px)—to pick out horizontal runs.
horiz_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (80, 1))
horiz_lines = cv2.morphologyEx(closed, cv2.MORPH_OPEN, horiz_kernel, iterations=1)

# ── 6) EXTRACT VERTICAL LINES ──
#    Use a very “tall” kernel—e.g. (width=1 px, height=80 px)—to pick out vertical runs.
vert_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 80))
vert_lines = cv2.morphologyEx(closed, cv2.MORPH_OPEN, vert_kernel, iterations=1)

# ── 7) COMBINE THE TWO MASKS INTO ONE “GRID” MASK ──
mask = cv2.add(horiz_lines, vert_lines)

# ── 8) DILATE ONCE OR TWICE ──
#    This helps ensure that any remaining thin/dashed bits get fully covered before inpainting.
kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
mask = cv2.dilate(mask, kernel_dilate, iterations=1)

# ── 9) INPAINT TO “ERASE” EVERY PIXEL IN THE MASK ──
#    INPAINT_TELEA often gives a smoother fill for large areas; radius=5 works fairly well here.
result = cv2.inpaint(img, mask, inpaintRadius=5, flags=cv2.INPAINT_TELEA)

# ── 10) WRITE OUT THE FINAL IMAGE ──
output_path = 'images/grid_removed.png'
cv2.imwrite(output_path, result)
print(f"Result saved to '{output_path}'")

# Optionally display it (uncomment these lines if you want to see it pop up)
# import matplotlib.pyplot as plt
# plt.figure(figsize=(8, 8))
# plt.imshow(cv2.cvtColor(result, cv2.COLOR_BGR2RGB))
# plt.axis('off')
# plt.show()
