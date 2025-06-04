import json
import numpy as np
import cv2 as cv
import os
from datetime import date, timedelta

def parse_ddd_to_date(year, doy):
    try:
        d = date(year, 1, 1) + timedelta(days=doy - 1)
        return f"{d.strftime('%Y_%m_%d')}_{doy}"
    except ValueError:
        return None


def find_sms(data):
    for ln in data["readResult"]["blocks"][0]["lines"]:
        if ln["text"] in ("SMS-2","SHS-2","SHE-2","SHB-2","SMS -2","SMS-7","SHS -2","SHS-","SMS-","SMS-Z","SHS -","sns-2","SHE-Z","SHE-","THE-Z"):
            return ln["boundingPolygon"][0]
    return None


def find_ON(data):
    for ln in data["readResult"]["blocks"][0]["lines"]:
        if any(sub in ln["text"] for sub in ("ON.", "OM.")):
            return ln["boundingPolygon"][0]
    return None

year = 1976
start_day = 183
satellite = "32A"

base = os.path.join(
    "/ships22/sds/goes/digitized",
    satellite,
    "vissr",
    str(year)
)

# Determine days in year
is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
max_day = 366 if is_leap else 365

missing_count = 0

for doy in range(start_day, max_day + 1):
    folder = parse_ddd_to_date(year, doy)
    if folder is None:
        continue

    full_path = os.path.join(base, folder)
    if not os.path.isdir(full_path):
        print(f"Missing directory: {full_path}")
        continue


    for file in os.listdir(full_path):
        if file.lower().endswith(".vi.thumb.png"):
            file_base = file.replace(".vi.thumb.png","")
            json_file = file_base + ".vi.json"
            with open(os.path.join(full_path, json_file), 'r') as json_file_obj:
                data = json.load(json_file_obj)

            coords = find_sms(data)
            if coords is None:
                coords = find_ON(data)
                if coords is None:
                    print(f"No SMS-2 or ON block in {json_file}")
                    continue
                coords["y"] = int(coords["y"]) - 14

            xshift = 660 - int(coords["x"])
            yshift = 55 - int(coords["y"])
            #print(full_path,xshift, yshift)
            img_path = os.path.join(full_path, file)
            img = cv.imread(img_path)
            if img is None:
                print(f"Failed to load image {img_path}")
                continue

            height, width = img.shape[:2]
            shift_height, shift_width = yshift * (height / 757), xshift * (width / 757)
            T = np.float32([[1, 0, shift_width], [0, 1, shift_height]])
            shifted = cv.warpAffine(img, T, (width, height))
            out_path = os.path.join(full_path, file_base + ".vi.thumb.shift.png")
            cv.imwrite(out_path, shifted)
            print(f"Wrote shifted image to {out_path}")
