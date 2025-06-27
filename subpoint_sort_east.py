import os
import re
import shutil
import json
from datetime import date, timedelta

# ───────────────────────────────────────────────────────────────────────────────
#                            U S E R CONFIGURATION
# ───────────────────────────────────────────────────────────────────────────────

DIR        = "/ships22/sds/goes/digitized"
MAIN_SAT   = "14A"
YEAR       = 1977
START_DAY  = 227  # process all days or set specific start

BASE_DIR   = os.path.join(DIR, f"{MAIN_SAT}/vissr/{YEAR}/grid_aligned/aligned_output_vi")
INPUT_DIR  = os.path.join(BASE_DIR, "aligned_with_grid")

# subfolders for combinations
SUBFOLDERS = [
    "5S74.5W", "0N74.5W", "5N74.5W",
    "5S75.0W", "0N75.0W", "5N75.0W",
    "5S75.5W", "0N75.5W", "5N75.5W",
    "other"
]
IMG_EXT    = ".png"

# patterns for latitude and longitude
LAT_PATTERNS = {
    "5N": [r"SN(?![OS])", r"5N(?!O)", r"SM(?![OS])"],
    "0N": [r"(?<!M)ON(?![O0])", r"0N(?!O)", r"OM(?!O)"],
    "5S": [r"SS", r"58", r"38", r"88", r"55", r"59", r"5S(?!E)"]
}
LON_PATTERNS = {
    "74.5W": [r"74\.5W", r"74\.5M", r"74\.50", r"74\.54"],
    "75.0W": [r"75\.0W", r"75\.OW", r"75\.04", r"75\.OM", r"75\.0V", r"75\. OM",
               r"75\.00", r"75\.DW", r"75\.ON", r"75\.OU", r"75\. OW",
               r"75\.OV"],
    "75.5W": [r"75\.5W", r"75\.5M", r"75\.5V", r"75\.50"]
}

# Helper to derive folder name from doy

def doy_folder(year, doy):
    d = date(year, 1, 1) + timedelta(days=doy-1)
    return d.strftime("%Y_%m_%d") + f"_{doy:03d}"

# ensure subfolders exist under INPUT_DIR
for sf in SUBFOLDERS:
    os.makedirs(os.path.join(INPUT_DIR, sf), exist_ok=True)


def find_lat_lon_from_json(json_path):
    try:
        data = json.load(open(json_path, 'r', errors='ignore'))
    except Exception:
        return None, None
    texts = []
    for block in data.get("readResult", {}).get("blocks", []):
        for line in block.get("lines", []):
            txt = line.get("text")
            if txt:
                texts.append(txt.upper())
    lat = None
    lon = None
    for key, pats in LAT_PATTERNS.items():
        for txt in texts:
            if any(re.search(p, txt) for p in pats):
                lat = key
                break
        if lat:
            break
    for key, pats in LON_PATTERNS.items():
        for txt in texts:
            if any(re.search(p, txt) for p in pats):
                lon = key
                break
        if lon:
            break
    return lat, lon

# iterate PNGs
for fname in sorted(os.listdir(INPUT_DIR)):
    if not fname.endswith(IMG_EXT):
        continue
    base = fname[:-len(IMG_EXT)]
    parts = base.split('.')  # e.g. ['14A','1977','227','180000']
    if len(parts) < 4:
        subfolder = "other"
    else:
        sat, year_str, doy_str, *_ = parts
        doy = int(doy_str)
        folder = doy_folder(int(year_str), doy)
        json_path = os.path.join(DIR, sat, "vissr", year_str, folder, base + ".vi.json")
        print(f"Checking JSON at: {json_path}")
        lat, lon = find_lat_lon_from_json(json_path)
        if lat and lon:
            candidate = f"{lat}{lon}"
            if candidate in SUBFOLDERS:
                subfolder = candidate
            else:
                subfolder = "other"
        else:
            subfolder = "other"
    src = os.path.join(INPUT_DIR, fname)
    dst = os.path.join(INPUT_DIR, subfolder, fname)
    if os.path.isfile(src):
        shutil.copy2(src, dst)
        print(f"Copied {fname} to {subfolder}/")
    else:
        print(f"Missing: {src}")

print("Done!")
