import tkinter as tk
import subprocess
import json
import os
import datetime
import re
import shutil

# Replace with your real Azure info
AZURE_KEY = "628fKIEshyzMxKZKxlKvxNsRtt5ZPqouq3NhDgm8ng8cOaWRPR7MJQQJ99BEACYeBjFXJ3w3AAAFACOGjWD4"
ENDPOINT_URL = (
    "https://scanned-image-text-ocr.cognitiveservices.azure.com/"
    "computervision/imageanalysis:analyze"
    "?features=caption,read"
    "&model-version=latest"
    "&language=en"
    "&api-version=2024-02-01"
)

# Manual satellite lookup
satellite_lookup = {
    'SMS-B': {'norad': '07648', 'intldes': '75011A'},
    'SMS-2': {'norad': '07648', 'intldes': '75011A'},
    'SMS-A': {'norad': '07298', 'intldes': '74033A'},
    'SMS-1': {'norad': '07298', 'intldes': '74033A'},
    'GOES-A': {'norad': '08366', 'intldes': '75100A'},
    'GOES-1': {'norad': '08366', 'intldes': '75100A'},
    'GOES 1': {'norad': '08366', 'intldes': '75100A'},
    'GOES-B': {'norad': '10061', 'intldes': '77048A'},
    'GOES-2': {'norad': '10061', 'intldes': '77048A'},
}

ocr_data = {}  # will hold the last OCR JSON
img_path = ""


root = tk.Tk()
root.title("TLE Creator from Scan")
root.geometry("450x400")

# Fields shown in UI = raw paper values
fields = [
    "Satellite Name", "Epoch Year", "Epoch Month", "Epoch Day", "Epoch Hours",
    "Eccentricity", "Inclination", "Mean Anomaly", "Argument of Perigee",
    "RAAN", "Anomalistic Period",  "Revolution Number"
]
entries = {}

# Build form
for idx, field in enumerate(fields):
    lbl = tk.Label(root, text=field + ":")
    lbl.grid(row=idx, column=0, sticky="e", padx=5, pady=2)
    ent = tk.Entry(root, width=30)
    ent.grid(row=idx, column=1, padx=5, pady=2)
    entries[field] = ent

def tle_checksum(line):
    s = sum(int(c) for c in line if c.isdigit()) + line.count('-')
    return str(s % 10)

def compute_mean_motion_derivatives(today_folder, sat_folder, mean_motion_today):
    """
    Returns: (first_deriv_float, second_deriv_float)
    """
    def parse_mean_motion_from_tle(tle_path):
        with open(tle_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines:
            if line.startswith('2 '):
                parts = line.strip().split()
                if len(parts) >= 8:
                    try:
                        return float(parts[-2])
                    except:
                        continue
        return None

    today = None
    folder_name = os.path.basename(today_folder)
    parts = folder_name.split('_')
    if len(parts) >= 4:
        yyyy, mm, dd = int(parts[0]), int(parts[1]), int(parts[2])
        today = datetime.date(yyyy, mm, dd)
    if not today:
        print("Could not parse date from folder name.")
        return (0.0, 0.0)

    base = os.path.dirname(os.path.dirname(today_folder))
    prev_mean_motions = []
    prev_dates = []

    days_back = 1
    max_days = 21
    while days_back <= max_days and len(prev_mean_motions) < 2:
        check_date = today - datetime.timedelta(days=days_back)
        yyyy_str = str(check_date.year)
        mm_str = f"{check_date.month:02d}"
        dd_str = f"{check_date.day:02d}"
        ddd = check_date.timetuple().tm_yday
        folder = os.path.join(base, yyyy_str, f"{yyyy_str}_{mm_str}_{dd_str}_{ddd}")
        if os.path.exists(folder):
            for file in os.listdir(folder):
                if file.endswith('.tle.txt') and sat_folder in file:
                    path = os.path.join(folder, file)
                    mean_motion = parse_mean_motion_from_tle(path)
                    if mean_motion:
                        prev_mean_motions.append(mean_motion)
                        prev_dates.append(check_date)
                        break
        days_back += 1

    if len(prev_mean_motions) < 2:
        print("Not enough data for derivatives; defaulting to zero")
        return (0.0, 0.0)

    days1 = (today - prev_dates[0]).days
    days2 = (prev_dates[0] - prev_dates[1]).days
    if days1 == 0 or days2 == 0:
        print("Invalid day gaps; defaulting to zero")
        return (0.0, 0.0)

    n_today = mean_motion_today
    n_prev1 = prev_mean_motions[0]
    n_prev2 = prev_mean_motions[1]

    first_deriv = (n_today - n_prev1) / days1
    second_deriv = (first_deriv - (n_prev1 - n_prev2) / days2) / days1

    # cap if too large
    if abs(first_deriv) > 0.0001:
        print(f"first derivative too large ({first_deriv}), setting to zero")
        first_deriv = 0.0
    if abs(second_deriv) > 0.0001:
        print(f"second derivative too large ({second_deriv}), setting to zero")
        second_deriv = 0.0

    return (first_deriv, second_deriv)


def scan_image_and_fill():
    # Scan
    result = subprocess.run(
        ["epsonscan2", "--scan", "./oscan.sf2"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    print("Scan output:", result.stdout)
    match = re.search(r'imageCount:(\d+)', result.stdout)
    if not match:
        print("Couldn't find imageCount in output.")
        return
    image_title = "img" + match.group(1)
    global img_path
    img_path = f"./oscimg/{image_title}.tiff"

    # OCR
    cmd = [
        "curl",
        "-H", f"Ocp-Apim-Subscription-Key: {AZURE_KEY}",
        "-H", "Content-Type: application/octet-stream",
        "--data-binary", f"@{img_path}",
        ENDPOINT_URL
    ]
    azure_result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
    )
    global ocr_data
    #print("OCR result:", azure_result.stdout)
    try:
        ocr_data = json.loads(azure_result.stdout)
    except json.JSONDecodeError:
        print("Failed to parse OCR JSON.")
        return

    # Save JSON
    os.makedirs("./oscjson", exist_ok=True)
    date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"./oscjson/{date_str}.json", "w", encoding="utf-8") as f:
        json.dump(ocr_data, f, indent=2)

    # Parse text lines
    lines = []
    for block in ocr_data['readResult']['blocks']:
        for line in block.get('lines', []):
            lines.append(line['text'])

    #print("OCR lines:", lines)

    # Flatten into single string, normalize
    text_all = ' '.join(lines).lower()
    text_all = re.sub(r'\s+', ' ', text_all)
    print("Flattened text:", text_all)
    text_all = re.sub(r'\s+', ' ', text_all)
    text_searchable = re.sub(r'[\s\.\(\)]', '', text_all)  # remove spaces, dots, and parentheses
    print("Normalized text_searchable:", text_searchable)

    # Step 1: find satellite name
    sat_name = "UNKNOWN"
    for name in satellite_lookup.keys():
        name_clean = re.sub(r'[\s\.]', '', name.lower())
        if name_clean in text_searchable:
            sat_name = name
            break

    # Step 2: helper to flexibly find number after a keyword
    def get_number_after(keyword):
        keyword_clean = re.sub(r'[\s\.\(\)]', '', keyword.lower())
        print("Trying keyword:", keyword_clean)
        if text_searchable.find(keyword_clean) == -1:
            return "0"


        # Build regex: keyword followed by optional space/dot, then capture number parts
        pattern = r'[\s\.\(\)]*'.join(map(re.escape, keyword.lower().split()))
        # capture one or more number parts possibly separated by spaces
        pattern += r'[\s\(\)]*([-\d\. ]+)'  # Allow spaces inside number

        m = re.search(pattern, text_all)
        if m:
            number_raw = m.group(1)
            # Remove spaces inside number like '1436. 23189' → '1436.23189'
            number = number_raw.replace(' ', '')
            return number
        else:
            return "0"

    # Step 3: get epoch parts (just find 'epoch' line if possible)
    epoch_line = next((l for l in lines if 'epoch' in l.lower()), "")
    parts = epoch_line.split()
    epoch_year = parts[1] if len(parts) > 1 else ''
    epoch_month = parts[3] if len(parts) > 3 else ''
    epoch_day = parts[5] if len(parts) > 5 else ''
    epoch_hour = parts[8].replace('H0.', '').strip() if len(parts) > 8 else '0'

    arg_of_perigee = get_number_after('ARG OF PERIFOCUS')
    if arg_of_perigee == "0":
        arg_of_perigee = get_number_after('ARGUMENT OF PERIGE DEG')
    if arg_of_perigee == "0":
        arg_of_perigee = get_number_after('ARGUMENT OF PERIGEE DEG')
    if arg_of_perigee == "0":
        arg_of_perigee = get_number_after('ARGUMENT OF PERIGEE')

    anom_period = get_number_after('ANOMALISTIC PERIOD')

    inclination = get_number_after('INCLINATION DEG')
    if inclination == "0":
        inclination = get_number_after("INCLINATION")

    eccentricity = get_number_after('ECCENTRICITY')
    if eccentricity == "0":
        eccentricity = get_number_after('ECCENTRICY')

    raan = get_number_after('ASC NODE DEG')
    if raan == "0":
        raan = get_number_after('ASC NODE')
    if raan == "0":
        raan = get_number_after('ASCEND NODE')



    mean_anom = get_number_after('MEAN ANOMALY DEG')
    if mean_anom == "0":
        mean_anom = get_number_after('MEAN ANOMALY')

    autofill = {
        "Satellite Name": sat_name,
        "Epoch Year": epoch_year,
        "Epoch Month": epoch_month,
        "Epoch Day": epoch_day,
        "Epoch Hours": epoch_hour,
        "Anomalistic Period": anom_period,
        "Inclination": inclination,
        "RAAN": raan,  # shorter flexible keyword
        "Eccentricity": eccentricity,
        "Argument of Perigee": arg_of_perigee,
        "Mean Anomaly": mean_anom,
        "Revolution Number": "100"
    }

    #print("Autofill parsed:", autofill)

    # Update UI
    for key, val in autofill.items():
        entries[key].delete(0, tk.END)
        entries[key].insert(0, val)

def confirm_and_output_tle():
    vals = {key: ent.get().strip() for key, ent in entries.items()}

    # Folder and header
    sat_raw = vals["Satellite Name"].upper()
    if 'SMS-A' in sat_raw or 'SMS-1' in sat_raw:
        sat_folder = 'sms01'
        sat_header = 'SMS-1'
    elif 'SMS-B' in sat_raw or 'SMS-2' in sat_raw:
        sat_folder = 'sms02'
        sat_header = 'SMS-2'
    elif 'GOES-A' in sat_raw or 'GOES-1' in sat_raw:
        sat_folder = 'goes01'
        sat_header = 'GOES-1'
    elif 'GOES-B' in sat_raw or 'GOES-2' in sat_raw:
        sat_folder = 'goes02'
        sat_header = 'GOES-2'
    else:
        sat_folder = 'unknown'
        sat_header = sat_raw

    sat = satellite_lookup.get(sat_header, {'norad': '00000', 'intldes': '00000A'})

    anom_period = float(vals["Anomalistic Period"])
    if anom_period == 0:
        anom_period = 1440
    mean_motion = round(1440 / anom_period, 8)
    ecc7 = vals["Eccentricity"].replace('.', '').ljust(7, '0')[:7]
    year = 1900 + int(vals["Epoch Year"])
    month = int(vals["Epoch Month"])
    day = int(vals["Epoch Day"])
    dt = datetime.datetime(year, month, day)
    ddd = dt.timetuple().tm_yday
    hrs = int(vals["Epoch Hours"] or "0")
    epoch_fraction = hrs / 24
    fraction_digits = f"{int(epoch_fraction * 1e8):08d}"
    epoch_str = f"{int(vals['Epoch Year']):02d}{ddd:03d}.{fraction_digits}"

    # Output folder
    out_base = "/ships22/sds/goes/digitized/TLE"
    yyyy = str(year)
    mm = f"{month:02d}"
    dd = f"{day:02d}"
    folder = os.path.join(out_base, sat_folder, yyyy, f"{yyyy}_{mm}_{dd}_{ddd}")
    os.makedirs(folder, exist_ok=True)

    # Compute derivatives
    first_deriv_val, second_deriv_val = compute_mean_motion_derivatives(folder, sat_folder, mean_motion)

    # Format first_deriv as decimal with sign and 8 places
    if first_deriv_val == 0:
        first_deriv_str = " .00000000"
    else:
        first_deriv_str = f"{first_deriv_val:.8f}"
        if first_deriv_val > 0:
            first_deriv_str = " " + first_deriv_str[1:]  # keep '.00000000'
        elif first_deriv_val < 0:
            first_deriv_str = first_deriv_str[2:]
            first_deriv_str = "-" + first_deriv_str


    # Format second_deriv as exponential, e.g., 00000+0
    def format_exp(val):
        if val == 0:
            return " 00000+0"
        exp = 0
        mant = val
        while abs(mant) < 1 and exp > -9:
            mant *= 10
            exp -= 1
        mant_int = int(round(mant * 1e5))
        return f"{abs(mant_int):05d}{exp:+d}".replace('+', '').replace('-', '-')  # ensure correct format
    second_deriv_str = format_exp(second_deriv_val)
    if second_deriv_val > 0:
        second_deriv_str = " " + second_deriv_str


    # Bstar drag term keep zero
    bstar = " 00000+0"

    # Build lines
    line1 = (
        f"1 {sat['norad']}U {sat['intldes']}   {epoch_str} {first_deriv_str} {second_deriv_str} {bstar} 0    0"
    )
    line2 = (
        f"2 {sat['norad']:>5} "
        f"{float(vals['Inclination']):8.4f} "
        f"{float(vals['RAAN']):8.4f} "
        f"{ecc7:>7} "
        f"{float(vals['Argument of Perigee']):8.4f} "
        f"{float(vals['Mean Anomaly']):8.4f} "
        f"{mean_motion:11.8f}"
        f"{int(vals['Revolution Number']):5d}"
    )

    # Add checksums
    line1 = line1[:68] + tle_checksum(line1)
    line2 = line2[:68] + tle_checksum(line2)

    print("\nGenerated TLE:")
    print(sat_header)
    print(line1)
    print(line2)

    # File names
    timestamp = f"{hrs:02}0000"
    img_filename = f"{sat_folder}.{yyyy}.{ddd}.{timestamp}.orbelem.tiff"
    tle_filename = f"{sat_folder}.{yyyy}.{ddd}.{timestamp}.tle.txt"
    json_filename = f"{sat_folder}.{yyyy}.{ddd}.{timestamp}.json"

    img_dst = os.path.join(folder, img_filename)
    try:
        shutil.copy(img_path, img_dst)
        print(f"Copied image to: {img_dst}")
    except Exception as e:
        print(f"Failed to copy image: {e}")

    tle_path = os.path.join(folder, tle_filename)
    with open(tle_path, "w", encoding="utf-8") as f:
        f.write(f"{sat_header}\n{line1}\n{line2}\n")
    print(f"Saved TLE to: {tle_path}")

    json_path = os.path.join(folder, json_filename)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(ocr_data, f, indent=2)
    print(f"Saved OCR JSON to: {json_path}")



btn_scan = tk.Button(root, text="Scan Image & Autofill", command=scan_image_and_fill)
btn_scan.grid(row=len(fields), column=0, pady=10)

btn_confirm = tk.Button(root, text="Confirm & Output TLE", command=confirm_and_output_tle)
btn_confirm.grid(row=len(fields), column=1, pady=10)

root.mainloop()
