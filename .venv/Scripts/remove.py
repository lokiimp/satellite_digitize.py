from rembg import remove
from PIL import Image, ImageDraw
import numpy as np

# load and remove background
input_path  = "images/32A.1976.284.204500.vi.med.png"
output_path = "images/removed_32A.1976.284.204500.vi.med2.png"
input_image = Image.open(input_path)
rgba        = remove(input_image).convert("RGBA")

# extract alpha channel as a 2D array
alpha = np.array(rgba)[:, :, 3]

# compute width at each row
widths = (alpha > 0).sum(axis=1)
y_max  = int(np.argmax(widths))

# get all x positions in that row that are opaque
xs = np.where(alpha[y_max] > 0)[0]

# find runs of consecutive xs
runs = []
start = xs[0]
prev  = xs[0]
for x in xs[1:]:
    if x == prev + 1:
        prev = x
    else:
        runs.append((start, prev))
        start = prev = x
runs.append((start, prev))

# pick the first run whose length >= 10
x_start = x_end = None
for a, b in runs:
    if (b - a + 1) >= 10:
        x_start, x_end = a, b
        break

if x_start is None:
    # fallback: just use the full span
    x_start, x_end = int(xs.min()), int(xs.max())

# center of that segment
x_center = (x_start + x_end) // 2

# draw
draw = ImageDraw.Draw(rgba)
green = (0, 255, 0, 255)

# draw line only from x_start to x_end
draw.line([(x_start, y_max), (x_end, y_max)], fill=green, width=2)

# draw center dot
r = 6
draw.ellipse(
    [(x_center - r, y_max - r), (x_center + r, y_max + r)],
    fill=green
)

rgba.save(output_path)
print(f"Drew line from x={x_start} to {x_end} at y={y_max}, center at x={x_center}")
