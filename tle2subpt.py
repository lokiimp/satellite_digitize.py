#!/usr/bin/env python3
import sys
import os
import datetime
import subprocess

if len(sys.argv) < 2:
    print("Usage: python tle_daily_subpoints.py SMS-1")
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

# Collect all available TLE dates
available_dates = {}
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
                tle_file = None
                for file in os.listdir(folder_path):
                    if file.endswith('.tle.txt') and sat_folder in file:
                        tle_file = os.path.join(folder_path, file)
                        break
                if tle_file:
                    available_dates[folder_date] = tle_file
            except ValueError:
                continue

if not available_dates:
    print("No TLE files found.")
    sys.exit(1)

# Determine first and last date in dataset
first_date = min(available_dates.keys())
last_date = max(available_dates.keys())

output_lines = []

# Loop through every day between first and last
curr_date = first_date
while curr_date <= last_date:
    # Pick nearest TLE on or before curr_date
    tle_date = max(d for d in available_dates.keys() if d <= curr_date)
    tle_file = available_dates[tle_date]

    # Run tle_to_subpoint2.bash
    date_str = curr_date.isoformat()
    result = subprocess.run(
        ["./tle_to_subpoint2.bash", tle_file, date_str, sat_name],
        capture_output=True, text=True
    )
    lat = lon = None
    for line in result.stdout.splitlines():
        if "00:00:00" in line:
            parts = line.strip().split()
            time_index = parts.index("00:00:00")
            lat = parts[time_index + 1]
            lon = parts[time_index + 2]
            break

    if lat and lon:
        ddd = curr_date.timetuple().tm_yday
        line = f"{sat_name} {curr_date.year} {ddd:03d} {lat} {lon}"
        print(line)
        output_lines.append(line)

    curr_date += datetime.timedelta(days=1)

# Save to file
output_file = f"{sat_folder}.sbpt"
with open(output_file, 'w') as f:
    f.write("\n".join(output_lines) + "\n")

print(f"\nComplete. Results saved to {output_file}")
