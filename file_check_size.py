import os
import re
from datetime import date, timedelta

def parse_ddd_to_date(year, doy):
    try:
        d = date(year, 1, 1) + timedelta(days=doy - 1)
        return f"{d.strftime('%Y_%m_%d')}_{doy:03}"
    except ValueError:
        return None

year       = int(input("enter start year: "))
start_day  = int(input("enter start day: "))
satellite  = input("enter satellite (e.g. 32A): ")

base = os.path.join(
    "/ships22/sds/goes/digitized",
    satellite,
    "vissr",
    str(year)
)

is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
max_day = 366 if is_leap else 365

pattern = re.compile(
    rf"^{re.escape(satellite)}\.{year}\.(\d{{1,3}})\.(\d{{6}})\.(ir|vi)\.(json|tiff|png)$"
)

TIFF_THRESHOLD = 415 * 1024 * 1024
PNG_THRESHOLD  = 160 * 1024 * 1024

missing_count = 0

for doy in range(start_day, max_day + 1):
    folder = parse_ddd_to_date(year, doy)
    if not folder:
        continue

    full_path = os.path.join(base, folder)
    if not os.path.isdir(full_path):
        missing_count += 1
        print(f"[{missing_count}/7] Missing directory: {full_path}")
        if missing_count >= 7:
            print("seven directories missing; aborting.")
            break
        continue

    missing_count = 0

    files_by_time = {}
    for fname in os.listdir(full_path):
        m = pattern.match(fname)
        if not m:
            #print(f"  → Unexpected name: {fname}")
            continue
        _, timecode, band, ext = m.groups()
        files_by_time.setdefault(timecode, {}) \
                     .setdefault(band, {}) \
                     .setdefault(ext, []) \
                     .append(fname)

    for tcode, bands in sorted(files_by_time.items()):
        for band, ext_map in bands.items():
            # now both IR and VI require json, tiff, and png
            expected = {"json", "tiff", "png"}

            found = set(ext_map.keys())
            missing = expected - found
            extra   = found - expected

            if missing or extra:
                print(f"  In {folder}, time {tcode}, band {band}:")
                if missing:
                    print(f"    • missing: {', '.join(sorted(missing))}")
                if extra:
                    print(f"    • unexpected: {', '.join(sorted(extra))}")

            for ext in ("tiff", "png"):
                if ext not in ext_map:
                    continue
                for fname in ext_map[ext]:
                    path = os.path.join(full_path, fname)
                    size = os.path.getsize(path)
                    thresh = TIFF_THRESHOLD if ext == "tiff" else PNG_THRESHOLD
                    if size < thresh:
                        mb = size / (1024*1024)
                        req = thresh / (1024*1024)
                        print(f"    ✗ {fname} is {mb:.1f} MiB; needs ≥ {req:.0f} MiB")
