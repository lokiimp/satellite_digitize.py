import os
import re
from datetime import date, timedelta

def parse_ddd_to_date(year, doy):
    try:
        d = date(year, 1, 1) + timedelta(days=doy - 1)
        return f"{d.strftime('%Y_%m_%d')}_{doy}"
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

# days in year
is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
max_day = 366 if is_leap else 365

# regex for files: sat.year.doy.timecode.band.ext
pattern = re.compile(
    rf"^{re.escape(satellite)}\.{year}\.(\d{{1,3}})\.(\d{{6}})\.(ir|vi)\.(json|tiff)$"
)

missing_count = 0

for doy in range(start_day, max_day + 1):
    folder = parse_ddd_to_date(year, doy)
    if not folder:
        continue

    full_path = os.path.join(base, folder)
    if not os.path.isdir(full_path):
        missing_count += 1
        print(f"[{missing_count}/3] Missing directory: {full_path}")
        if missing_count >= 3:
            print("Three directories missing; aborting.")
            break
        continue

    # reset if you only want consecutive misses
    missing_count = 0

    # collect files by timestamp code
    files_by_time = {}
    for fname in os.listdir(full_path):
        m = pattern.match(fname)
        if not m:
            print(f"  → Unexpected name: {fname}")
            continue
        _, timecode, band, ext = m.groups()
        files_by_time.setdefault(timecode, {}).setdefault(band, set()).add(ext)

    # now check each timecode group
    for tcode, bands in files_by_time.items():
        for band, exts in bands.items():
            expected_exts = {"json", "tiff"}
            missing = expected_exts - exts
            extra   = exts - expected_exts
            if missing or extra:
                print(f"  In {folder}, time {tcode}, band {band}:")
                if missing:
                    print(f"    • missing: {', '.join(sorted(missing))}")
                if extra:
                    print(f"    • unexpected ext: {', '.join(sorted(extra))}")
