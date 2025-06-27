import os
import re
import shutil

# ───────────────────────────────────────────────────────────────────────────────
#                            U S E R CONFIGURATION
# ───────────────────────────────────────────────────────────────────────────────

BASE_DIR   = "/ships22/sds/goes/digitized/13A/vissr/1977/grid_aligned/aligned_output_vi"
INPUT_DIR  = os.path.join(BASE_DIR, "aligned_with_grid")
TXT_FILE   = os.path.join(BASE_DIR, "output.txt")   # REPLACE THIS

# subfolders to create under INPUT_DIR
SUBFOLDERS = [".5S74.5W",".0N74.5W",".5N74.5W",".5S75.0W",".0N75.0W",".5N75.0W",".5S75.5W",".0N75.5W",".5N75.5W","other"]

IMG_EXT    = ".png"

# match lines like:
#   Processed 32A.1978.001.204500: …, sub=5N
LINE_RE    = re.compile(r"Processed\s+(\S+):.*sub=(\d+)([NS])")

# ───────────────────────────────────────────────────────────────────────────────

# 1) Make sure sub‐folders exist in the aligned_with_grid folder
for sf in SUBFOLDERS:
    os.makedirs(os.path.join(INPUT_DIR, sf), exist_ok=True)

# 2) Parse each line of output.txt
with open(TXT_FILE, "r") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("ERROR"):
            continue

        m = LINE_RE.match(line)
        if not m:
            continue
        #TODO implement something like this for searching for both N and W offset:
        # patterns = {
        #     "74.5W": ["74.5W", "74.5M", "74.50", "74.54"],
        #     "75.0W": ["75.OW", "75.04", "75.OM", "75.0V", "75. OM", "75.00", "75.DW", "75.ON",
        #               "75.OU", "75. OW", "75.0M", "75. ON", "75. 00"],
        #     "75.5W": ["75.5W", "75.5M", "75.5V", "75.50", ],
        # }
        #
        # # 4) Search in priority order
        # for result, pats in patterns.items():
        #     for snippet in texts:
        #         for pat in pats:
        #             if re.search(pat, snippet):
        #                 return result
        # patterns = {
        #     "5N": [r"SN(?![OS])", r"5N(?!O)", r"SM(?![OS])"],  # don't match SN or 5N if followed by 'O'
        #     "0N": [r"(?<!M)ON(?!O)", r"0N(?!O)", r"OM(?!O)"],  # don't match ON or 0N if followed by 'O'
        #     "5S": [r"SS", r"58", r"38", r"88", r"55", r"59", r"5S(?!E)"]  # don't match 5S if followed by 'E'
        # }
        # TODO and then put it into the folder that corresponds to both values, and other if there isn't such a folder

        base_name, digit, ns = m.groups()
        subfolder = f".{digit}{ns}"   # e.g. ".5N"

        if subfolder not in SUBFOLDERS:
            continue

        src = os.path.join(INPUT_DIR, base_name + IMG_EXT)
        dst = os.path.join(INPUT_DIR, subfolder, base_name + IMG_EXT)

        if not os.path.isfile(src):
            print(f"Missing image: {src}")
            continue

        shutil.copy2(src, dst)
        print(f"Copied {base_name+IMG_EXT} → {subfolder}/")

print("Done!")
