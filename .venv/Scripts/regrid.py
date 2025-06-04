import cv2
import numpy as np

# 1. load and convert to gray
img = cv2.imread("images/32A.1976.284.204500.vi.med.png")
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# 2. threshold to pick out the bright grid lines
_, th = cv2.threshold(gray, 230, 255, cv2.THRESH_BINARY)

# 3. clean up with morphology (make lines solid)
kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5,5))
mask = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel)

# 4. optionally detect long straight lines (if you want exact locations)
#lines = cv2.HoughLinesP(mask, 1, np.pi/180, threshold=100,minLineLength=200, maxLineGap=10)
#
# if lines is not None:
#     for x1, y1, x2, y2 in lines.reshape(-1, 4):
#         cv2.line(mask, (x1, y1), (x2, y2), 255, 5)


# 5. inpaint to “erase” the old grid
clean = cv2.inpaint(img, mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)



cv2.imwrite("images/cleaned.png", clean)
