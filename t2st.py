#!/usr/bin/env python3
import sys
import os
import datetime
import subprocess

if len(sys.argv) < 4:
    print("Usage: python tle.py SAT_NAME START_DATE INTERVAL")
    print("Example: python tle.py ATS-3 1977-06-01 0:15")
    sys.exit(1)

sat_name = sys.argv[1].upper()  # e.g., SMS-1
start_date_str = sys.argv[2]    # e.g., 1977-06-01
interval_str = sys.argv[3]      # e.g., 0:15

# Parse the interval as hours:minutes
try:
    h, m = map(int, interval_str.split(":"))
    interval = datetime.timedelta(hours=h, minutes=m)
except Exception:
    print("Interval must be in format H:M, e.g., 0:15 for 15 minutes.")
    sys.exit(1)

sat_folder_map = {
    'SMS-1': 'sms01',
    'SMS-A': 'sms01',
    'SMS-2': 'sms02',
    'SMS-B': 'sms02',
    'GOES-1': 'goes01',
    'GOES-A': 'goes01',
    'GOES-2': 'goes02',
    'GOES-B': 'goes02',
    'ATS-3': 'ats03'
}

sat_folder = sat_folder_map.get(sat_name)
if not sat_folder:
    print(f"Unknown satellite name: {sat_name}")
    sys.exit(1)

base_dir = "/data/oper/autonav/TLE_FILES"
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

first_date = min(available_dates.keys())
last_date = max(available_dates.keys())

try:
    start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
except Exception:
    print("Start date must be in format YYYY-MM-DD")
    sys.exit(1)

# Loop through every interval between first and last, for each year
curr_dt = max(start_date, datetime.datetime.combine(first_date, datetime.time(0, 0)))
end_dt = datetime.datetime.combine(last_date, datetime.time(23, 59))

output_lines_by_year = {}

while curr_dt <= end_dt:
    curr_date = curr_dt.date()
    curr_time = curr_dt.time()
    # Pick nearest TLE on or before curr_date
    tle_date = max(d for d in available_dates.keys() if d <= curr_date)
    tle_file = available_dates[tle_date]

    print(f"\nProcessing {curr_date} {curr_time.strftime('%H:%M:%S')} using TLE {tle_date}")

    # Format date string as ISO with time
    date_str = curr_dt.strftime("%Y-%m-%d")
    time_arg_str = curr_dt.strftime("%-H:%M")  # use %H:%M if zero-padding required
    day_arg = f"DAY={date_str}"
    time_arg = f"TIME={time_arg_str}"

    cmd = ["./tle_to_subpoint_time.bash", tle_file, day_arg, time_arg, sat_name]
    print("Running:", " ".join(cmd))

    result = subprocess.run(cmd, capture_output=True, text=True)

    # Debug output (optional)
    # print(result.stdout)
    # print(result.stderr)

    time_str = curr_dt.strftime("%H:%M:%S")
    lat = lon = None
    for line in result.stdout.splitlines():
        if time_str in line:
            parts = line.strip().split()
            if len(parts) >= 5:
                lat = parts[2]
                lon = parts[3]
            break

    if lat and lon:
        ddd = curr_date.timetuple().tm_yday
        out_line = f"{sat_name} {curr_date.year} {ddd:03d} {curr_time.strftime('%H:%M:%S')} {lat} {lon}"
        year_str = str(curr_date.year)
        output_lines_by_year.setdefault(year_str, []).append(out_line)
        print(out_line)
    else:
        print(f"No match found for {time_str}")

    curr_dt += interval

#Save to separate files per year
for year_str, year_lines in output_lines_by_year.items():
    out_file = os.path.join(os.getcwd(), f"{sat_folder}_{year_str}_{interval_str}.sbpt")
    with open(out_file, 'w') as f:
        f.write("\n".join(year_lines) + "\n")
    print(f"Saved {len(year_lines)} lines to {out_file}")

print("\nComplete. One file written per year.")