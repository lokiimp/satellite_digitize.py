#!/usr/bin/env python3
import os
import re

base_dir = "/ships22/sds/goes/digitized/TLE"

# TLE format regex (line 1 & line 2 rules)
tle_line1_pattern = re.compile(
    r"^1\s+\d{5}[A-Z]\s+[A-Z0-9]{5,8}\s+\d{5}\.\d{8}\s+[ \+\-]\.\d{8}\s+\d{5}[+\-]\d\s+\d{5}[+\-]\d\s+\d\s+\d{4}$"
)
tle_line2_pattern = re.compile(
    r"^2 \d{5} [ +-]\d{2}\.\d{4} [ +-]\d{3}\.\d{4} \d\.\d{7} [ +-]\d{3}\.\d{4} [ +-]\d{3}\.\d{4} \d\.\d{8} \d{5}$"
)

def validate_tle_file(filepath):
    with open(filepath, "r") as f:
        lines = [l.rstrip("\n") for l in f.readlines()]

    if len(lines) < 3:
        return False, "Too few lines"

    name, l1, l2 = lines[0], lines[1], lines[2]

    # Length checks
    if len(l1) != 69:
        return False, f"Line 1 length {len(l1)} != 69"
    if len(l2) != 69:
        return False, f"Line 2 length {len(l2)} != 69"

    # Regex checks
    if not tle_line1_pattern.match(l1):
        return False, "Line 1 format invalid"
    if not tle_line2_pattern.match(l2):
        return False, "Line 2 format invalid"

    return True, None

errors = []

# Walk through satellites
for sat in sorted(os.listdir(base_dir)):
    sat_dir = os.path.join(base_dir, sat)
    if not os.path.isdir(sat_dir):
        continue

    for year in sorted(os.listdir(sat_dir)):
        year_dir = os.path.join(sat_dir, year)
        if not os.path.isdir(year_dir):
            continue

        for day_folder in sorted(os.listdir(year_dir)):
            day_dir = os.path.join(year_dir, day_folder)
            if not os.path.isdir(day_dir):
                continue

            # Find TLE file
            tle_file = None
            for file in os.listdir(day_dir):
                if file.endswith(".tle.txt"):
                    tle_file = os.path.join(day_dir, file)
                    break

            if not tle_file:
                errors.append(f"{sat} {day_folder}: Missing TLE file")
                continue

            valid, msg = validate_tle_file(tle_file)
            if not valid:
                errors.append(f"{sat} {day_folder}: {msg}")

# Output results
if errors:
    print("Invalid TLEs found:")
    for err in errors:
        print("  " + err)
else:
    print("All TLEs are valid.")
