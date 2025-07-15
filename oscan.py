import tkinter as tk
import subprocess
import json
import os
import datetime
import re

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
    'GOES-B': {'norad': '10061', 'intldes': '77048A'},
    'GOES-2': {'norad': '10061', 'intldes': '77048A'},
}

root = tk.Tk()
root.title("TLE Creator from Scan")
root.geometry("450x400")

# Fields shown in UI = raw paper values
fields = [
    "Satellite Name", "Epoch Year", "Epoch Month", "Epoch Day", "Epoch Hours",
    "Anomalistic Period", "Inclination", "RAAN", "Eccentricity",
    "Argument of Perigee", "Mean Anomaly", "Revolution Number"
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
    text_searchable = re.sub(r'[\s\.]', '', text_all)  # remove spaces & dots

    # Step 1: find satellite name
    sat_name = "UNKNOWN"
    for name in satellite_lookup.keys():
        name_clean = re.sub(r'[\s\.]', '', name.lower())
        if name_clean in text_searchable:
            sat_name = name
            break

    # Step 2: helper to flexibly find number after a keyword
    def get_number_after(keyword):
        keyword_clean = re.sub(r'[\s\.]', '', keyword.lower())
        if text_searchable.find(keyword_clean) == -1:
            return "0"

        # Build regex: keyword followed by optional space/dot, then capture number parts
        pattern = r'[\s\.]*'.join(map(re.escape, keyword.lower().split()))
        # capture one or more number parts possibly separated by spaces
        pattern += r'\s*([-\d\. ]+)'

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
    epoch_year = parts[1] if len(parts) > 1 else '75'
    epoch_month = parts[3] if len(parts) > 3 else '11'
    epoch_day = parts[5] if len(parts) > 5 else '30'
    epoch_hour = parts[8].replace('H0.', '').strip() if len(parts) > 8 else '0'

    autofill = {
        "Satellite Name": sat_name,
        "Epoch Year": epoch_year,
        "Epoch Month": epoch_month,
        "Epoch Day": epoch_day,
        "Epoch Hours": epoch_hour,
        "Anomalistic Period": get_number_after('ANOMALISTIC PERIOD'),
        "Inclination": get_number_after('INCLINATION'),
        "RAAN": get_number_after('ASCEND NODE'),  # shorter flexible keyword
        "Eccentricity": get_number_after('ECCENTRICITY'),
        "Argument of Perigee": get_number_after('ARG OF PERIFOCUS'),
        "Mean Anomaly": get_number_after('MEAN ANOMALY'),
        "Revolution Number": "547"
    }

    #print("Autofill parsed:", autofill)

    # Update UI
    for key, val in autofill.items():
        entries[key].delete(0, tk.END)
        entries[key].insert(0, val)

def confirm_and_output_tle():
    vals = {key: ent.get().strip() for key, ent in entries.items()}

    # Convert to TLE-specific data:
    sat = satellite_lookup.get(vals["Satellite Name"], {'norad': '00000', 'intldes': '00000A'})
    anom_period = float(vals["Anomalistic Period"])
    mean_motion = round(1440 / anom_period, 8)
    ecc7 = vals["Eccentricity"].replace('.', '').ljust(7, '0')[:7]

    year = 1900 + int(vals["Epoch Year"])
    month = int(vals["Epoch Month"])
    day = int(vals["Epoch Day"])
    dt = datetime.datetime(year, month, day)
    ddd = dt.timetuple().tm_yday
    epoch_str = f"{vals['Epoch Year']}{ddd:03d}.00000000"

    first_deriv = '00000-0'
    second_deriv = '00000+0'

    line1 = (
        f"1 {sat['norad']}U {sat['intldes']}   {epoch_str}  .00000000  {first_deriv} {second_deriv} 0    0"
    )
    line2 = (
        f"2 {sat['norad']} {float(vals['Inclination']):8.4f} {float(vals['RAAN']):8.4f} {ecc7} "
        f"{float(vals['Argument of Perigee']):8.4f} {float(vals['Mean Anomaly']):8.4f} "
        f"{mean_motion:11.8f} {vals['Revolution Number']}"
    )

    # Checksums
    line1 = line1[:68] + tle_checksum(line1)
    line2 = line2[:68] + tle_checksum(line2)

    print("\nGenerated TLE:")
    print(line1)
    print(line2)

btn_scan = tk.Button(root, text="Scan Image & Autofill", command=scan_image_and_fill)
btn_scan.grid(row=len(fields), column=0, pady=10)

btn_confirm = tk.Button(root, text="Confirm & Output TLE", command=confirm_and_output_tle)
btn_confirm.grid(row=len(fields), column=1, pady=10)

root.mainloop()
