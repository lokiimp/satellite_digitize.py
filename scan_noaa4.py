import tkinter as tk
import shutil
import os
from datetime import datetime, timedelta
import subprocess

SATELLITE = "noaa4"
out_base_path = "/ships22/sds"

# The fixed scan combos in order:
COMBINATIONS = [
    ("vi", "so", "da"),
    ("vi", "no", "da"),
    ("ir", "so", "da"),
    ("ir", "no", "da"),
    ("ir", "so", "ni"),
    ("ir", "no", "ni"),
]

root = tk.Tk()
root.title('NOAA-4 Image Scanner')
root.geometry("800x200")

tk.Label(root, text="Input Image Metadata:", font=("Arial", 10)).pack(pady=10)
frame = tk.Frame(root)
frame.pack(pady=10)

# Date
tk.Label(frame, text="Date (MM/DD/YY):").grid(row=0, column=0, padx=5)
date_entry = tk.Entry(frame)
date_entry.grid(row=0, column=1, padx=5)

# North/South Dropdown
tk.Label(frame, text="Hemisphere:").grid(row=0, column=2, padx=5)
ns_var = tk.StringVar(value="no")
ns_menu = tk.OptionMenu(frame, ns_var, "no", "so")
ns_menu.grid(row=0, column=3, padx=5)

# Day/Night Dropdown
tk.Label(frame, text="Day/Night:").grid(row=0, column=4, padx=5)
dn_var = tk.StringVar(value="da")
dn_menu = tk.OptionMenu(frame, dn_var, "da", "ni")
dn_menu.grid(row=0, column=5, padx=5)

# Band Dropdown
tk.Label(frame, text="Band:").grid(row=0, column=6, padx=5)
band_var = tk.StringVar(value="vi")
band_menu = tk.OptionMenu(frame, band_var, "vi", "ir")
band_menu.grid(row=0, column=7, padx=5)


def get_current_combo_index(band, ns, dn):
    try:
        return COMBINATIONS.index((band, ns, dn))
    except ValueError:
        return 0  # fallback to first combo if invalid


def get_next_combo(band, ns, dn):
    idx = get_current_combo_index(band, ns, dn)
    if idx < len(COMBINATIONS) - 1:
        return COMBINATIONS[idx + 1], False  # next combo, no date increment
    else:
        return COMBINATIONS[0], True  # cycle back to first combo, increment date


def increment_date(date_str):
    try:
        dt = datetime.strptime(date_str, "%m/%d/%y")
        next_dt = dt + timedelta(days=1)
        return next_dt.strftime("%m/%d/%y")
    except ValueError:
        print("Invalid date format. Use MM/DD/YY.")
        return date_str


def button_press():
    process_image()


def process_image():
    date_text = date_entry.get().strip()
    band = band_var.get()
    dn = dn_var.get()
    ns = ns_var.get()

    if not date_text:
        print("Date must be filled.")
        return

    try:
        dt = datetime.strptime(date_text, "%m/%d/%y")
    except ValueError:
        print("Invalid date format. Use MM/DD/YY.")
        return

    year = dt.strftime("%Y")
    month = dt.strftime("%m")
    day = dt.strftime("%d")
    ddd = dt.strftime("%j")

    new_filename = f"{SATELLITE}.{year}.{ddd}.{ns}.{dn}.{band}.tiff"
    folder = os.path.join(out_base_path, SATELLITE, year, f"{year}_{month}_{day}_{ddd}")
    os.makedirs(folder, exist_ok=True)
    new_path = os.path.join(folder, new_filename)

    scan_file = "./viscan.sf2" if band == "vi" else "./irscan.sf2"
    print(f"Starting scan using {scan_file}...")

    result = subprocess.run(
        ["epsonscan2", "--scan", scan_file],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )

    if result.returncode == 0:
        src = os.path.join(os.getcwd(), "fullimage", "img.tiff")
        if not os.path.exists(src):
            print(f"Scan completed but image not found at {src}")
            return

        shutil.copy(src, new_path)
        os.remove(src)
        print(f"Saved: {new_path}")

        # Auto-advance
        next_combo, roll_over = get_next_combo(band, ns, dn)
        band_var.set(next_combo[0])
        ns_var.set(next_combo[1])
        dn_var.set(next_combo[2])

        if roll_over:
            new_date = increment_date(date_text)
            date_entry.delete(0, tk.END)
            date_entry.insert(0, new_date)

    else:
        print("Scan failed:", result.stderr)


tk.Button(root, text="Submit", command=button_press).pack(pady=10)

root.mainloop()
