import tkinter as tk
import shutil
import os
from datetime import datetime, timedelta
from PIL import Image, ImageTk
import threading
import subprocess
import re
import json


TEST = False

month_abbr_num = {
        'JA': 1, 'FE': 2, 'MR': 3, 'AP': 4, 'MY': 5, 'JN': 6,
        'JL': 7, 'AU': 8, 'SE': 9, 'OC': 10, 'NO': 11, 'DE': 12
    }

month_abbr_txt = {
        'JA': '01', 'FE': '02', 'MR': '03', 'AP': '04', 'MY': '05', 'JN': '06',
        'JL': '07', 'AU': '08', 'SE': '09', 'OC': '10', 'NO': '11', 'DE': '12'
    }
AZURE_KEY    = "628fKIEshyzMxKZKxlKvxNsRtt5ZPqouq3NhDgm8ng8cOaWRPR7MJQQJ99BEACYeBjFXJ3w3AAAFACOGjWD4"
ENDPOINT_URL = (
    "https://scanned-image-text-ocr.cognitiveservices.azure.com/"
    "computervision/imageanalysis:analyze"
    "?features=caption,read"
    "&model-version=latest"
    "&language=en"
    "&api-version=2024-02-01"
)


root = tk.Tk()
root.title('Satellite Image Scanner')
root.geometry("700x150")

# Title label
title_label = tk.Label(root, text="Input Image Data:", anchor=tk.CENTER, font=("Arial", 10), fg="black")
title_label.pack(pady=10)

# Frame for input fields
input_frame = tk.Frame(root)
input_frame.pack(pady=10)

# Time input
time_label = tk.Label(input_frame, text="Time:")
time_label.grid(row=0, column=0, padx=5, pady=5)
time_entry = tk.Entry(input_frame)
time_entry.grid(row=0, column=1, padx=5, pady=5)

# Date input
date_label = tk.Label(input_frame, text="Date:")
date_label.grid(row=0, column=2, padx=5, pady=5)
date_entry = tk.Entry(input_frame)
date_entry.grid(row=0, column=3, padx=5, pady=5)

# Satellite input
satellite_label = tk.Label(input_frame, text="Satellite:")
satellite_label.grid(row=0, column=4, padx=5, pady=5)
satellite_entry = tk.Entry(input_frame)
satellite_entry.grid(row=0, column=5, padx=5, pady=5)


def button_press():
    vals = process_image()



    satellite_text = vals[0]
    prefix = satellite_text[:3]  # e.g., "32A" or "33A"
    suffix = satellite_text[3:]  # e.g., "-2" or "-Z"

    if suffix == "-2":
        new_suffix = "-Z"
        txt = time_entry.get()
        txt = txt[:2] + ":" + txt[2:]
        time_entry.delete(0, tk.END)
        time_entry.insert(0, txt)

    elif suffix == "-Z":
        new_suffix = "-2"
        time_entry.delete(0, tk.END)
    else:
        new_suffix = ""  # fallback if it's something unexpected

    # Update the satellite text and entry
    new_satellite_text = prefix + new_suffix
    satellite_entry.delete(0, tk.END)
    satellite_entry.insert(0, new_satellite_text)

    # If toggled to second satellite ("-Z"), update the date
    if new_suffix == "-2" and suffix == "-Z":
        date_text = vals[1]
        date_text = increment_date(date_text)
        date_entry.delete(0, tk.END)
        date_entry.insert(0, date_text)
    return

# Function to handle file renaming
def process_image():
    result = subprocess.run(
        [
            "epsonscan2",
            "--scan",
            "/home/sgunshor/scanning/epsonscan2-bundle-6.7.70.0.x86_64.rpm/quickscan.sf2"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,  # returns str instead of bytes
    )

    if result.returncode == 0:
        # Look for the pattern "imageCount:<number>"
        match = re.search(r'imageCount:(\d+)', result.stdout)
        if match:
            number = match.group(1)
            image_title = "img" + number
            print(f"Extracted: {image_title}")
        else:
            print("Couldn't find image count in output.")
    else:
        print(f"Command failed with code {result.returncode}")
        print("Error output:", result.stderr)
    time_text = time_entry.get().strip()
    date_text = date_entry.get().strip()
    satellite_text = satellite_entry.get().strip()

    if not image_title or not time_text or not date_text or not satellite_text:
        print("All fields must be filled!")
        return []

    # Search for file in current directory
    for file in os.listdir("images"):
        if file.startswith(image_title):
            corrected_vals = check_against_ocr(file, satellite_text, date_text, time_text)
            satellite_text = corrected_vals[0][:3]
            date_text = corrected_vals[1]
            year = "19" + date_text[4:]
            ddd = parse_ddd(date_text)
            time_text = corrected_vals[2]
            month = date_text[2:6]
            if corrected_vals[0][4:5] == '2':
                band = 'vi'
            elif corrected_vals[0][4:5] == 'Z':
                band = 'ir'
            else:
                print("error: band is not 2 or Z")
            file_extension = os.path.splitext(file)[1]
            new_filename = f"{satellite_text}.{year}.{ddd}.{time_text}00.{band}{file_extension}"
            json_filename = f"{satellite_text}.{year}.{ddd}.{time_text}00.{band}.json"
            year_folder = os.path.join(os.getcwd(), year)
            date_folder_string = f"{year}_{month_abbr_txt.get(date_text[2:4])}_{date_text[0:2]}_{ddd}"
            date_folder = os.path.join(year, date_folder_string)
            if not os.path.exists(year_folder):
                os.makedirs(year_folder)
            if not os.path.exists(date_folder):
                os.makedirs(date_folder)
            new_path = os.path.join(date_folder, new_filename)
            json_path = os.path.join(date_folder, json_filename)

            def on_scan_done(result):
                if result.returncode == 0:
                    image_dir = os.path.join(os.getcwd(), "fullimage")
                    src = os.path.join(image_dir, "img.tiff")
                    shutil.copy(src, new_path)
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(corrected_vals[3], f, indent=2, ensure_ascii=False)
                    if os.path.exists(src):
                        os.remove(src)
                else:
                    print("Scan failed:", result.stderr)

            if band == 'vi':
                scan_args = ["epsonscan2", "--scan", "/home/.../viscan.sf2"]
            elif band == 'ir':
                scan_args = ["epsonscan2", "--scan", "/home/.../irscan.sf2"]
            show_spinner(os.path.join(os.path.join(os.getcwd(), 'images'),file), scan_args, on_scan_done, win_size=(300,300))
            print(f"File copied and renamed to: {date_folder}/{new_filename}")
            return corrected_vals

    print("File not found!")

def increment_date(date_str):
    month_abbr = ["JA", "FB", "MR", "AP", "MY", "JN", "JL", "AU", "SE", "OC", "NV", "DC"]
    month_map = {abbr: i + 1 for i, abbr in enumerate(month_abbr)}

    day = int(date_str[:2])
    month = date_str[2:4]
    year = int(date_str[4:])

    if month not in month_map:
        raise ValueError("Invalid month abbreviation")

    month_num = month_map[month]

    full_year = 1900 + year if year >= 50 else 2000 + year  # Adjusting for 2-digit year format

    date_obj = datetime(full_year, month_num, day) + timedelta(days=1)

    new_day = date_obj.day
    new_month_abbr = list(month_map.keys())[date_obj.month - 1]
    new_year = date_obj.year % 100  # Convert back to two-digit format

    return f"{new_day:02}{new_month_abbr}{new_year:02}"

def check_against_ocr(file, satellite_text, date_text, time_text):
    img_path = os.path.join(os.getcwd(), "images", file)

    cmd = [
        "curl",
        "-H", f"Ocp-Apim-Subscription-Key: {AZURE_KEY}",
        "-H", "Content-Type: application/octet-stream",
        "--data-binary", f"@{img_path}",  # use the full path, with @
        ENDPOINT_URL  # no extra quotes here
    ]
    print(cmd)
    # run the process, capture stdout/stderr, return text
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        check=True
    )

    azure_output = json.loads(result.stdout)
    print(azure_output)
    vals = get_first_line_text(azure_output).split()
    print(vals)

    if time_text not in vals:
        time_index = -1  # default if not found
    else:
        time_index = vals.index(time_text)

    if time_index == -1:
        time_text = open_problem_window(time_text, vals[1])
        if date_text not in vals:
            date_text = open_problem_window(date_text, vals[2])
        if satellite_text not in vals:
            satellite_text = open_problem_window(satellite_text, vals[3])
    else:
        if date_text not in vals:
            date_text = open_problem_window(date_text, vals[time_index + 1])
        if satellite_text not in vals:
            satellite_text = open_problem_window(satellite_text, vals[time_index + 2])
    if ":" in time_text:
        time_text = time_text.replace(":", "")
    return [satellite_text, date_text, time_text, azure_output]

def get_first_line_text(analyze_result):
    try:
        blocks = analyze_result["readResult"]["blocks"]
        first_block = blocks[0]
        first_line = first_block["lines"][0]
        return first_line["text"]
    except (KeyError, IndexError):
        return None


def open_problem_window(user_text, ocr_text):
    problem_window = tk.Toplevel(root)
    problem_window.title("OCR Error")
    problem_window.geometry("400x200")
    problem_window.grab_set()

    tk.Label(problem_window, text="OCR Mismatch:", font=("Arial", 12, "bold")).pack(pady=5)
    tk.Label(problem_window, text=f"OCR detected: {ocr_text}", font=("Arial", 10)).pack(pady=5)
    tk.Label(problem_window, text="Correct value:", font=("Arial", 10)).pack(pady=5)

    fix_entry = tk.Entry(problem_window, font=("Arial", 10))
    fix_entry.pack(pady=5)
    fix_entry.insert(0, user_text)

    response_var = tk.StringVar()

    def confirm_correction():
        response_var.set(fix_entry.get())
        problem_window.destroy()

    tk.Button(problem_window, text="Confirm", command=confirm_correction).pack(pady=10)

    problem_window.wait_variable(response_var)

    return response_var.get()


def parse_ddd(date):
    # Days in each month, normal year
    month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

    # Parse input
    day = int(date[:2])
    month_code = date[2:4]
    year_suffix = int(date[4:])
    year = 1900 + year_suffix  # Assuming years are 1900-1999

    # Leap year check
    def is_leap(yr):
        return yr % 4 == 0 and (yr % 100 != 0 or yr % 400 == 0)

    if is_leap(year):
        month_days[1] = 29  # February has 29 days in a leap year

    # Get the month index (1-based -> 0-based)
    month_index = month_abbr_num.get(month_code)
    if not month_index:
        raise ValueError("Invalid month code")

    # Calculate total days passed
    total_days = sum(month_days[:month_index - 1]) + day
    return total_days

def show_spinner(file_path, scan_args, on_done, win_size=(300, 300), padding=20):
    spinner_win = tk.Toplevel(root)
    spinner_win.title("Scanning…")
    w, h = win_size
    spinner_win.geometry(f"{w}x{h}")
    spinner_win.transient(root)
    spinner_win.grab_set()

    pil_img = Image.open(file_path)
    max_w, max_h = w - padding, h - padding
    pil_img.thumbnail((max_w, max_h), Image.ANTIALIAS)
    tk_img = ImageTk.PhotoImage(pil_img)
    label = tk.Label(spinner_win, image=tk_img)
    label.image = tk_img
    label.pack(expand=True)

    angle = 0
    def rotate_frame():
        nonlocal angle, tk_img
        angle = (angle + 30) % 360
        rotated = pil_img.rotate(angle, expand=True)
        tk_img = ImageTk.PhotoImage(rotated)
        label.configure(image=tk_img)
        label.image = tk_img
        spinner_win.after(100, rotate_frame)

    def do_scan_and_wait():
        # start the scan (which forks/backgrounds)
        subprocess.Popen(scan_args)

        # now poll for the output file
        image_dir = os.path.join(os.getcwd(), "fullimage")
        src = os.path.join(image_dir, "img.tiff")

        # wait for the file to appear
        while not os.path.exists(src):
            time.sleep(0.5)

        # wait until its size stops changing for a few iterations
        last_size = -1
        stable_count = 0
        while stable_count < 3:
            try:
                size = os.path.getsize(src)
            except OSError:
                size = -1
            if size == last_size:
                stable_count += 1
            else:
                stable_count = 0
                last_size = size
            time.sleep(0.5)

        # once stable, do your on_done and close spinner
        def finish():
            on_done(src)
            spinner_win.destroy()
        root.after(0, finish)

    rotate_frame()
    threading.Thread(target=do_scan_and_wait, daemon=True).start()




# Submit Buttont
submit_button = tk.Button(root, text="Submit", command=button_press)
submit_button.pack(pady=10)

root.mainloop()
