#!/usr/bin/env python3
import sys
import os
import datetime
import subprocess
import re

if len(sys.argv) < 2:
    print("Usage: python tle_batch_compare.py SMS-1")
    sys.exit(1)

sat_name = sys.argv[1].upper()  # e.g., SMS-1

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

dates_and_folders = []
for year_dir in sorted(os.listdir(sat_dir)):
    year_path = os.path.join(sat_dir, year_dir)
    if not os.path.isdir(year_path):
        continue
    for folder in sorted(os.listdir(year_path)):
        folder_path = os.path.join(year_path, folder)
        if not os.path.isdir(folder_path):
            continue
        parts = folder.split('_')
        if len(parts) >= 4:
            yyyy, mm, dd = parts[0], parts[1], parts[2]
            try:
                folder_date = datetime.date(int(yyyy), int(mm), int(dd))
                dates_and_folders.append((folder_date, folder_path))
            except:
                continue

dates_and_folders.sort()

output_file = f"{sat_folder}.sbpt"
all_lines = []
errors = []
prev_lat = None
prev_lon = None
prev_date = None

for folder_date, folder_path in dates_and_folders:
    tle_file = None
    for file in os.listdir(folder_path):
        if file.endswith('.tle.txt') and sat_folder in file:
            tle_file = os.path.join(folder_path, file)
            break

    if not tle_file:
        continue

    date_str = folder_date.isoformat()
    result = subprocess.run(["./tle_to_subpoint2.bash", tle_file, date_str, sat_name], capture_output=True, text=True)
    output = result.stdout

    all_lines.append(f"=== {date_str} ===")
    all_lines.append(output)

    lat = lon = None
    for line in output.splitlines():
        if "00:00:00" in line:
            parts = line.strip().split()
            try:
                time_index = parts.index("00:00:00")
                lat = parts[time_index + 1]
                lon = parts[time_index + 2]
            except:
                continue

    if lat and lon:
        def dms_to_deg(s):
            match = re.match(r'([+-]?)(\d+):(\d+):(\d+)', s)
            if not match:
                return 0.0
            sign, d, m, s = match.groups()
            deg = int(d) + int(m)/60 + int(s)/3600
            if sign == '-':
                deg = -deg
            return deg

        lat_deg = dms_to_deg(lat)
        lon_deg = dms_to_deg(lon)

        if prev_lat is not None:
            lat_diff = abs(lat_deg - prev_lat)
            lon_diff = abs(lon_deg - prev_lon)
            if lat_diff > 3.0 or lon_diff > 3.0:
                errors.append(f"!!! {date_str} — LAT DIFF: {lat_diff:.2f}°, LON DIFF: {lon_diff:.2f}°")

        prev_lat = lat_deg
        prev_lon = lon_deg
        prev_date = folder_date

with open(output_file, 'w') as f:
    f.write('\n'.join(all_lines))
    if errors:
        f.write('\n\n=== ERRORS ===\n')
        f.write('\n'.join(errors))

print(f"Complete. Output saved to {output_file}")