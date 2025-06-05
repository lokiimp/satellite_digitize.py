import os
from datetime import date, timedelta

def parse_ddd_to_date(year, doy):
    try:
        d = date(year, 1, 1) + timedelta(days=doy - 1)
        return f"{d.strftime('%Y_%m_%d')}_{doy:03}"
    except ValueError:
        return None

year = int(input("enter start year: "))
start_day = int(input("enter start day: "))
satellite = input("enter satellite (e.g. 32A): ")

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
        missing_count += 1
        print(f"[{missing_count}/10] Missing directory: {full_path}")
        if missing_count >= 10:
            print("Ten directories missing; aborting.")
            break
        continue

    # reset missing counter if you want to only count *consecutive* misses:
    missing_count = 0

    num_files = len(os.listdir(full_path))
    if num_files < 10:
        print(f"Error at {full_path}: only {num_files} files (need ≥10)")
