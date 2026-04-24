#!/usr/bin/env python3
import sys
import os
import re
import datetime
import subprocess

# ----------------------------
# Helpers
# ----------------------------

DATE_FOLDER_RE = re.compile(r'^(\d{4})_(\d{2})_(\d{2})(?:_[0-9A-Za-z]+)?$')

def parse_interval(interval_str: str) -> datetime.timedelta:
    try:
        h, m = map(int, interval_str.split(":"))
        return datetime.timedelta(hours=h, minutes=m)
    except Exception:
        print("Interval must be in format H:M, e.g., 0:15 for 15 minutes.")
        sys.exit(1)

def is_probable_tle_file(path: str) -> bool:
    """
    Check if file likely contains at least one TLE pair (lines starting with '1 ' then '2 ').
    """
    try:
        line1_seen = False
        with open(path, 'r', errors='ignore') as f:
            for line in f:
                s = line.strip()
                if s.startswith('1 ') and len(s) > 10:
                    line1_seen = True
                elif line1_seen and s.startswith('2 ') and len(s) > 10:
                    return True
        return False
    except Exception:
        return False

def extract_lat_lon_from_line(line: str):
    """
    Try to extract latitude/longitude from a line by finding any consecutive float pair
    where lat in [-90, 90] and lon in [-180, 180].
    """
    nums = re.findall(r'[-+]?\d+(?:\.\d+)?', line)
    for i in range(len(nums) - 1):
        try:
            lat = float(nums[i])
            lon = float(nums[i + 1])
            if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                return (f"{lat:.6f}", f"{lon:.6f}")
        except ValueError:
            continue
    return (None, None)

def find_tle_in_folder(folder_path: str, sat_folder: str, yyyy: int, doy: int):
    """
    Find TLE file in folder matching the convention:
      satcode.YYYY.DDD.HHMMSS.tle.txt  (case-insensitive)
    e.g., ats03.1969.025.000000.tle.txt

    If multiple exist for the same day with different HHMMSS, pick the one with the latest HHMMSS.
    Returns absolute path or None.
    """
    if not os.path.isdir(folder_path):
        return None

    sat = sat_folder.lower()
    target_year = f"{yyyy:04d}"
    target_doy = f"{doy:03d}"

    # Regex: ^sat\.YYYY\.DDD\.(\d{6})\.tle\.txt$
    pattern = re.compile(
        rf'^{re.escape(sat)}\.{target_year}\.{target_doy}\.(\d{{6}})\.tle\.txt$',
        re.IGNORECASE
    )

    candidates = []  # (HHMMSS int, fullpath)
    for fn in os.listdir(folder_path):
        m = pattern.match(fn)
        if not m:
            continue
        hhmmss_str = m.group(1)
        try:
            hhmmss = int(hhmmss_str)  # e.g., 000000 -> 0, 235959 -> 235959
        except ValueError:
            continue
        full = os.path.join(folder_path, fn)
        if os.path.isfile(full):
            candidates.append((hhmmss, full))

    if not candidates:
        return None

    # Choose the latest time-of-day TLE for that date
    candidates.sort(key=lambda t: t[0], reverse=True)
    for _, path in candidates:
        if is_probable_tle_file(path):
            return path

    # Fallback: return best-named file even if we couldn't verify TLE content
    return candidates[0][1]

# ----------------------------
# Main
# ----------------------------

if len(sys.argv) < 4:
    print("Usage: python tle.py SAT_NAME START_DATE INTERVAL")
    print("Example: python tle.py ATS-3 1977-06-01 0:15")
    sys.exit(1)

sat_name = sys.argv[1].upper()   # e.g., ATS-3
start_date_str = sys.argv[2]     # e.g., 1977-06-01
interval_str = sys.argv[3]       # e.g., 0:15

interval = parse_interval(interval_str)

# Map human SAT_NAME to folder code
sat_folder_map = {
    'SMS-1': 'sms01',
    'SMS-A': 'sms01',
    'SMS-2': 'sms02',
    'SMS-B': 'sms02',
    'GOES-1': 'goes01',
    'GOES-A': 'goes01',
    'GOES-2': 'goes02',
    'GOES-B': 'goes02',
    'ATS-3': 'ats03',
}
sat_folder = sat_folder_map.get(sat_name)
if not sat_folder:
    print(f"Unknown satellite name: {sat_name}")
    sys.exit(1)

base_dir = "/data/oper/autonav/TLE_FILES"
sat_dir = os.path.join(base_dir, sat_folder)

if not os.path.isdir(sat_dir):
    print(f"Satellite directory not found: {sat_dir}")
    sys.exit(1)

# Collect all available TLEs by date
available_dates = {}  # date -> tle_file
for year_dir in sorted(os.listdir(sat_dir)):
    year_path = os.path.join(sat_dir, year_dir)
    if not os.path.isdir(year_path):
        continue
    if not year_dir.isdigit() or len(year_dir) != 4:
        continue

    year_int = int(year_dir)

    for folder in sorted(os.listdir(year_path)):
        folder_path = os.path.join(year_path, folder)
        if not os.path.isdir(folder_path):
            continue

        m = DATE_FOLDER_RE.match(folder)
        if not m:
            continue

        yyyy, mm, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            folder_date = datetime.date(yyyy, mm, dd)
        except ValueError:
            continue
        if yyyy != year_int:
            continue

        # Compute DOY to match filename (ats03.YYYY.DDD.HHMMSS.tle.txt)
        doy = folder_date.timetuple().tm_yday

        tle_file = find_tle_in_folder(folder_path, sat_folder, yyyy, doy)
        if tle_file:
            # If multiple sequences for the same day (e.g., _001, _025), the later folder
            # in sort order will overwrite and we keep the last found TLE file for that day.
            available_dates[folder_date] = tle_file

if not available_dates:
    print("No TLE files found under:", sat_dir)
    sys.exit(1)

first_date = min(available_dates.keys())
last_date = max(available_dates.keys())

try:
    start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
except Exception:
    print("Start date must be in format YYYY-MM-DD")
    sys.exit(1)

# Loop from the later of (start_date, first available TLE date) until last_date inclusive
curr_dt = max(start_date, datetime.datetime.combine(first_date, datetime.time(0, 0)))
end_dt = datetime.datetime.combine(last_date, datetime.time(23, 59))

output_lines_by_year = {}

while curr_dt <= end_dt:
    curr_date = curr_dt.date()
    curr_time = curr_dt.time()

    # Select TLE date on or before current date
    tle_candidates = [d for d in available_dates.keys() if d <= curr_date]
    if not tle_candidates:
        curr_dt += interval
        continue

    tle_date = max(tle_candidates)
    tle_file = available_dates[tle_date]

    print(f"\nProcessing {curr_date} {curr_time.strftime('%H:%M:%S')} using TLE {tle_date} ({os.path.basename(tle_file)})")

    # Use zero-padded hour/min for consistency
    date_str = curr_dt.strftime("%Y-%m-%d")
    time_arg_str = curr_dt.strftime("%H:%M")
    day_arg = f"DAY={date_str}"
    time_arg = f"TIME={time_arg_str}"

    cmd = ["./tle_to_subpoint_time.bash", tle_file, day_arg, time_arg, sat_name]
    print("Running:", " ".join(cmd))

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("Subprocess failed:", result.stderr.strip())
        curr_dt += interval
        continue

    # Match both padded and non-padded time strings
    time_str_padded = curr_dt.strftime("%H:%M:%S")
    time_str_unpadded = f"{curr_dt.hour}:{curr_dt.minute:02d}:{curr_dt.second:02d}"

    lat = lon = None
    for line in result.stdout.splitlines():
        if time_str_padded in line or time_str_unpadded in line:
            lat, lon = extract_lat_lon_from_line(line)
            if lat and lon:
                break

    if lat and lon:
        ddd = curr_date.timetuple().tm_yday
        out_line = f"{sat_name} {curr_date.year} {ddd:03d} {curr_time.strftime('%H:%M:%S')} {lat} {lon}"
        year_str = str(curr_date.year)
        output_lines_by_year.setdefault(year_str, []).append(out_line)
        print(out_line)
    else:
        print(f"No lat/lon match found for time {time_str_padded}")

    curr_dt += interval

# Save to separate files per year
for year_str, year_lines in output_lines_by_year.items():
    out_file = os.path.join(os.getcwd(), f"{sat_folder}_{year_str}_{interval_str.replace(':','')}.sbpt")
    with open(out_file, 'w') as f:
        f.write("\n".join(year_lines) + "\n")
    print(f"Saved {len(year_lines)} lines to {out_file}")

print("\nComplete. One file written per year (if any lines were produced).")