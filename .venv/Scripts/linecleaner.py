import cv2
import numpy as np

# 1) load & gray
img   = cv2.imread("images/32A.1976.284.204500.vi.med.png")
gray  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# 2) detect edges
edges = cv2.Canny(gray, 50, 150)

# 3) detect straight lines (grid)
lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=200,
                        minLineLength=200, maxLineGap=10)

# 4) detect circular arc (Earth limb)
circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1.2, minDist=100,
                           param1=100, param2=30, minRadius=300, maxRadius=400)

# 5) make a blank mask, draw those features onto it
feat = np.zeros_like(gray, dtype=np.uint8)

if lines is not None:
    for x1,y1,x2,y2 in lines.reshape(-1,4):
        cv2.line(feat, (x1,y1), (x2,y2), 255, 2)

if circles is not None:
    for x,y,r in circles[0]:
        cv2.circle(feat, (int(x),int(y)), int(r), 255, 2)

# 6) collect brightness values *only* at those feature pixels
ys, xs = np.where(feat>0)
vals   = gray[ys, xs]

# 7) choose your lower‐threshold as e.g. the 5th percentile
lw = int(np.percentile(vals, 5))
print(lw)
# 8) build your white‐mask off that
lower = np.array([lw]*3, dtype=np.uint8)
upper = np.array([255]*3, dtype=np.uint8)
mask  = cv2.inRange(img, lower, upper)

brush_size = 5
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (brush_size, brush_size))
mask_dilated = cv2.dilate(mask, kernel, iterations=1)

# 4. paint those masked pixels bright green (BGR = (0,255,0))
img[mask_dilated > 0] = (0, 255, 0)

# the “green” we painted (B, G, R)
GREEN = np.array((0,255,0), dtype=np.uint8)
img[mask_dilated > 0] = (0, 255, 0)

# 5. save result
cv2.imwrite(f"images/line_recolored_brush{brush_size}low{lw}.png", img)

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
numiterations = 0
# iterate until mask is empty or no progress
while True:
    img, changed = fill_green_once(img, mask)
    # rebuild mask
    mask = np.all(img == GREEN, axis=2)
    numiterations += 1
    print(numiterations)
    if not changed or not mask.any():
        break

cv2.imwrite(f"images/line_inpaintedbrush{brush_size}low{lw}.png", img)
