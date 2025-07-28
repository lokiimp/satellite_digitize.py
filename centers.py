import re
import os

# === USER CONFIGURATION ===
INPUT_PATH = "/arc25/arcdata/alpha/goes/pregvar/sms02/vissr/1978/grid_aligned/aligned_output_vi_4/output.txt"
OUTPUT_PATH = "/arc25/arcdata/alpha/goes/pregvar/centerpoints/1978westcenters.txt"
OLD_SAT_NAME = "32A"
NEW_SAT_NAME = "sms02"
OLD_SAT_NAME2 = "33A"
NEW_SAT_NAME2 = "goes01"
OLD_SAT_NAME3 = "35A"
NEW_SAT_NAME3 = "goes03"

# === Mask center positions for different subs ===
MASK_CENTERS = {
    "5N": (1032, 1116),
    "0N": (1032, 1114),
    "5S": (1030, 1111),
}

# Constants
FULL_SIZE = 12109
MED_SIZE = 2000
SCALE = FULL_SIZE / MED_SIZE  # ~6.0545

# Regex pattern to match each processed line
pattern = re.compile(r"Processed (\S+): θ=([-0-9.]+), dx=([-0-9.]+), dy=([-0-9.]+), score=\d+, sub=([A-Z0-9]+)")

with open(INPUT_PATH, "r") as infile, open(OUTPUT_PATH, "w") as outfile:
    for line in infile:
        match = pattern.search(line)
        if not match:
            continue

        filename = match.group(1)
        theta = float(match.group(2))
        dx = float(match.group(3))
        dy = float(match.group(4))
        sub = match.group(5)

        # Get the correct mask center for the subregion
        if sub not in MASK_CENTERS:
            print(f"Warning: Unknown sub '{sub}' in line: {line.strip()}")
            continue

        center_x, center_y = MASK_CENTERS[sub]

        # Unshifted center in .med.png coordinates
        unshifted_x = center_x + dx
        unshifted_y = center_y + dy

        # Scale to full-size image coordinates
        full_x = round(unshifted_x * SCALE)
        full_y = round(unshifted_y * SCALE)

        # Fix satellite name prefix
        base = os.path.splitext(os.path.basename(filename))[0]
        if base.startswith(OLD_SAT_NAME):
            base = base.replace(OLD_SAT_NAME, NEW_SAT_NAME, 1)
        if base.startswith(OLD_SAT_NAME2):
            base = base.replace(OLD_SAT_NAME2, NEW_SAT_NAME2, 1)
        if base.startswith(OLD_SAT_NAME3):
            base = base.replace(OLD_SAT_NAME3, NEW_SAT_NAME3, 1)

        outfile.write(f"{base}: {full_x}, {full_y}, θ = {theta:.2f}\n")

print(f"Done. Saved to: {OUTPUT_PATH}")