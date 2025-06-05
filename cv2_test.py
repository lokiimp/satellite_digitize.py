import cv2
import numpy as np
import matplotlib.pyplot as plt

# Load the image
image_path = "images/test2.tif"  # Replace with your image path
image = cv2.imread(image_path)

# Convert to grayscale
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

# Apply Gaussian blur to reduce noise
blurred = cv2.GaussianBlur(gray, (15, 15), 0)

# Use Canny edge detection to find edges in the image
edges = cv2.Canny(blurred, 50, 150)

# Find contours (edges that form shapes)
contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

# Try to find the largest contour, which we assume to be the top half of the circle
max_contour = max(contours, key=cv2.contourArea)

# Get the bounding box of the largest contour to estimate the region
x, y, w, h = cv2.boundingRect(max_contour)

# Now, let's filter the points that are in the upper half of the bounding box (this will be the top half of the circle)
top_half_points = []

# Iterate over the points in the largest contour
for point in max_contour:
    px, py = point[0]
    # Keep only points that lie in the upper half of the bounding box (above the center line)
    if py <= y + h // 2:
        top_half_points.append((px, py))

# Draw the top half points
for px, py in top_half_points:
    cv2.circle(image, (px, py), 1, (0, 255, 0), 2)

# Now let's reconstruct the bottom half by mirroring the top half
# We assume the center of the circle is along the middle of the bounding box
center_x = x + w // 2
center_y = y + h // 2
radius = h // 2  # Using the height of the bounding box to estimate radius

# Mirror the top half points to create the bottom half
for px, py in top_half_points:
    # Mirror the point across the center line of the circle
    mirror_y = 2 * center_y - py
    cv2.circle(image, (px, mirror_y), 1, (0, 0, 255), 2)

# Draw the full circle by connecting the points (approximated)
# Draw a circle around the reconstructed points for visualization
cv2.circle(image, (center_x, center_y), radius, (0, 255, 0), 2)

# Show the result
plt.imshow(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
plt.axis('off')
plt.show()
