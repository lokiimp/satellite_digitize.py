import tkinter as tk
import subprocess
import json
import re

# Replace these with your real Azure key and endpoint
AZURE_KEY = "628fKIEshyzMxKZKxlKvxNsRtt5ZPqouq3NhDgm8ng8cOaWRPR7MJQQJ99BEACYeBjFXJ3w3AAAFACOGjWD4"
ENDPOINT_URL = (
    "https://scanned-image-text-ocr.cognitiveservices.azure.com/"
    "computervision/imageanalysis:analyze"
    "?features=caption,read"
    "&model-version=latest"
    "&language=en"
    "&api-version=2024-02-01"
)

root = tk.Tk()
root.title("TLE Creator from Scan")
root.geometry("400x400")

# Labels for fields you’d expect in a TLE:
fields = [
    "Satellite Number", "Epoch Year", "Epoch Month", "Epoch Day", "Epoch Hours",
    "Mean Motion", "Inclination", "RAAN", "Eccentricity",
    "Argument of Perigee", "Mean Anomaly", "Revolution Number"
]
entries = {}

# Build form:
for idx, field in enumerate(fields):
    lbl = tk.Label(root, text=field + ":")
    lbl.grid(row=idx, column=0, sticky="e", padx=5, pady=2)
    ent = tk.Entry(root, width=30)
    ent.grid(row=idx, column=1, padx=5, pady=2)
    entries[field] = ent


def scan_image_and_fill():
    # Run scan (epsonscan2 with ./oscan.sf2)
    result = subprocess.run(
        ["epsonscan2", "--scan", "./oscan.sf2"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    print("Scan complete:", result.stdout)

    # For demonstration, assume output is named ./fullimage/img.tiff
    match = re.search(r'imageCount:(\d+)', result.stdout)
    if match:
        number = match.group(1)
        image_title = "img" + number
        print(f"Extracted: {image_title}")
    else:
        print("Couldn't find image count in output.")
    img_path = f"./oscimg/{image_title}.tiff"

    # Send to Azure OCR:
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

    print("OCR result:", azure_result.stdout)
    ocr_data = json.loads(azure_result.stdout)

    # Example: get text from first block, first line:
    text = ""
    try:
        text = ocr_data["readResult"]["blocks"][0]["lines"][0]["text"]
    except Exception:
        print("Could not parse OCR text")

    print("OCR text:", text)

    # Here you would use regex to extract numbers from OCR text
    # For now, just fake data:
    fake_data = {
        "Satellite Number": "07648",
        "Epoch Year": "75",
        "Epoch Month": "11",
        "Epoch Day": "30",
        "Epoch Hours": "0",
        "Mean Motion": "1.00270745",
        "Inclination": "0.4920",
        "RAAN": "281.3560",
        "Eccentricity": "0003160",
        "Argument of Perigee": "205.1690",
        "Mean Anomaly": "171.8770",
        "Revolution Number": "547"
    }
    # Autofill:
    for key, val in fake_data.items():
        entries[key].delete(0, tk.END)
        entries[key].insert(0, val)


def confirm_and_output_tle():
    # Collect values:
    vals = {key: ent.get().strip() for key, ent in entries.items()}
    # Build TLE lines:
    # Epoch: YYDDD.DDD...
    # For now, build DDD:
    month = int(vals["Epoch Month"])
    day = int(vals["Epoch Day"])
    # crude way to compute day of year:
    import datetime
    dt = datetime.datetime(1900 + int(vals["Epoch Year"]), month, day)
    ddd = dt.timetuple().tm_yday
    epoch_str = f"{vals['Epoch Year']}{ddd:03d}.00000000"

    # First line:
    line1 = (
        f"1 {vals['Satellite Number']}U 75011A   {epoch_str}  .00000000  00000-0  00000+0 0 0000"
    )
    # Second line:
    line2 = (
        f"2 {vals['Satellite Number']} {vals['Inclination']:>8} {vals['RAAN']:>8} {vals['Eccentricity']:>7} "
        f"{vals['Argument of Perigee']:>8} {vals['Mean Anomaly']:>8} {vals['Mean Motion']:>11} {vals['Revolution Number']}"
    )
    print("\nGenerated TLE:")
    print(line1)
    print(line2)


# Buttons:
btn_scan = tk.Button(root, text="Scan Image & Autofill", command=scan_image_and_fill)
btn_scan.grid(row=len(fields), column=0, pady=10)

btn_confirm = tk.Button(root, text="Confirm & Output TLE", command=confirm_and_output_tle)
btn_confirm.grid(row=len(fields), column=1, pady=10)

root.mainloop()
