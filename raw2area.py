import os
import re
import subprocess
import shutil

# Set the base directory to walk through
BASE_DIR = "/arc25/arcdata/alpha/goes/pregvar"

# Satellite subsystem mapping (satellite + band)
SAT_SS_MAPPING = {
    "sms01": {"vi": 16, "ir": 17},
    "sms02": {"vi": 18, "ir": 19},
    "goes01": {"vi": 20, "ir": 21},
    "goes02": {"vi": 22, "ir": 23},
    "goes03": {"vi": 24, "ir": 25},
    # Add more as needed
}

AREA = 1002
dataset_ref = f"A/A.{AREA}"
area_filename = f"AREA{AREA}"
mcidas_output_path = os.path.join("/arc25/arcdata/alpha/goes/pregvar", area_filename)

# Image dimensions
LINES = 12109
ELEMENTS = 12109

# Regex pattern to match raw filenames
FILENAME_PATTERN = re.compile(r"(?P<sat>.+)\.(?P<year>\d{4})\.(?P<doy>\d{3})\.(?P<hhmmss>\d{6})\.(?P<band>vi|ir)\.raw$")

for root, dirs, files in os.walk(BASE_DIR):
    dirs.sort()
    files.sort()
    for file in files:
        if not file.endswith(".raw"):
            continue

        match = FILENAME_PATTERN.match(file)
        if not match:
            print(f"Skipping unrecognized file: {file}")
            continue

        groups = match.groupdict()
        sat = groups["sat"].lower()
        year = groups["year"]
        doy = groups["doy"]
        hhmmss = groups["hhmmss"]
        band = groups["band"].lower()

        # Parse hhmmss into HH:MM:SS
        hh, mm, ss = hhmmss[:2], hhmmss[2:4], hhmmss[4:6]
        day_param = f"{year}{doy}"
        time_param = f"{hh}:{mm}:{ss}"
        memo = sat.upper()
        memo = memo.replace("0","-")

        # Look up SS value
        ss_value = SAT_SS_MAPPING.get(sat, {}).get(band)
        if ss_value is None:
            print(f"Warning: Unknown SS value for {sat} {band}. Skipping.")
            continue

        # Input and output paths
        raw_path = os.path.join(root, file)

        # Final output file in same folder as .raw
        final_area_name = file.replace(".raw", ".area")
        final_area_path = os.path.join(root, final_area_name)

        # Skip if .area already exists
        if os.path.exists(final_area_path):
            continue

        # Run imgmake.k
        command = [
            "imgmake.k", raw_path, dataset_ref,
            str(LINES), str(ELEMENTS),
            f"DAY={day_param}",
            f"TIME={time_param}",
            "DEV=CCC",
            f"MEMO={memo}",
            f"SS={ss_value}"
        ]

        try:
            print(f"Creating AREA file: {file} → {final_area_name}")
            subprocess.run(command, check=True)

            # Copy to final .area path and remove
            shutil.copy(mcidas_output_path, final_area_path)
            os.remove(mcidas_output_path)

        except subprocess.CalledProcessError as e:
            print(f"Error running imgmake.k for {file}: {e}")
        except Exception as e:
            print(f"Error handling output file for {file}: {e}")
