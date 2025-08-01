#!/usr/bin/env python3
import sys
import os
import datetime
import subprocess
import re

# Usage check
if len(sys.argv) < 2:
    print("Usage: python check_all_subpoints.py SMS-1")
    sys.exit(1)

sat_name = sys.argv[1].upper()

# Satellite folder map
sat_folder_map = {
    'SMS-1': 'sms01',
    'SMS-A': 'sms01',
    'SMS-2': 'sms02',
    'SMS-B': 'sms02',
    'GOES-1': 'goes01',
    'GOES-A': 'goes01',
    'GOES-2': 'goes02',
    'GOES-B': 'goes02'
}

sat_folder = sat_folder_map.get(sat_name)
if not sat_folder:
    print(f"Unknown satellite name: {sat_name}")
    sys.exit(1)

base_dir = "/ships22/sds/goes/digitized/TLE"
sat_dir = os.path.join(base_dir, sat_folder)
out_file = f"{sat_name}_subpoint_check.txt"

all_outputs = []

# Collect all folder dates
folders = []
for year_dir in sorted(os.listdir(sat_dir)):
    year_path = os.path.join(sat_dir, year_dir)
    if not os.path.isdir(year_path):
        continue
    for folder in sorted(os.listdir(year_path)):
        parts = folder.split('_')
        if len(parts) >= 4:
            try:
                yyyy, mm, dd = map(int, parts[:3])
                folder_date = datetime.date(yyyy, mm, dd)
                folders.append((folder_date, os.path.join(year_path, folder)))
            except:
                continue

folders.sort()

# Run each day
for date_obj, folder_path in folders:
    tle_file = None
    for file in os.listdir(folder_path):
        if file.endswith('.tle.txt') and sat_folder in file:
            tle_file = os.path.join(folder_path, file)
            break

    if not tle_file:
        continue

    date_str = date_obj.strftime("%Y-%m-%d")
    print(f"Running for {date_str}...")
    try:
        result = subprocess.run([
            "./tle_to_subpoint2.bash",
            tle_file,
            date_str,
            sat_name
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        all_outputs.append(f"=== {date_str} ===\n" + result.stdout)
    except Exception as e:
        print(f"Error for {date_str}: {e}")

# Parsing helpers
def dms_to_decimal(dms: str) -> float:
    sign = -1 if dms.startswith('-') else 1
    parts = list(map(float, dms.strip('-').split(':')))
    degrees = parts[0] + parts[1] / 60 + parts[2] / 3600
    return sign * degrees

def parse_blocks(text):
    entries = []
    blocks = re.split(r"\n=+ (\d{4}-\d{2}-\d{2}) =+\n", text)
    for i in range(1, len(blocks), 2):
        date = blocks[i]
        block = blocks[i + 1]
        lat_match = re.search(r"latitude\s+([\-\d:]+)", block)
        lon_match = re.search(r"longitude\s+([\d:]+)", block)
        if lat_match and lon_match:
            lat = dms_to_decimal(lat_match.group(1))
            lon = dms_to_decimal(lon_match.group(1))
            entries.append((date, lat, lon))
    return entries

def flag_large_differences(entries, threshold=3.0):
    issues = []
    for i in range(1, len(entries)):
        prev_date, prev_lat, prev_lon = entries[i - 1]
        curr_date, curr_lat, curr_lon = entries[i]
        dlat = abs(curr_lat - prev_lat)
        dlon = abs(curr_lon - prev_lon)
        if dlat > threshold or dlon > threshold:
            issues.append(
                f"{curr_date}: Δlat={dlat:.2f}°, Δlon={dlon:.2f}° (from {prev_date})")
    return issues

# Parse and flag
combined_text = "\n".join(all_outputs)
entries = parse_blocks(combined_text)
alerts = flag_large_differences(entries)

# Write to file
with open(out_file, "w") as f:
    f.write(combined_text)
    f.write("\n\n=== ALERTS OVER 3 DEG ===\n")
    for alert in alerts:
        f.write(alert + "\n")

print(f"Analysis complete. Output written to {out_file}")
