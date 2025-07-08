import tkinter as tk
import shutil
import os
from datetime import datetime, timedelta
import subprocess
import re
import json

TEST = False

out_base_path = "/ships22/sds/goes/digitized"

# This list defines the automated workflow. Each tuple is (Time, Band Type).
SCAN_SEQUENCE = [
    ('06:00', 'IR'),
    ('14:00', 'IR'),
    ('14:00', 'VIS'),
    ('18:00', 'IR'),
    ('18:00', 'VIS'),
    ('23:00', 'IR'),
    ('23:00', 'VIS'),
]

month_abbr_num = {
    'JA': 1, 'FE': 2, 'MR': 3, 'AP': 4, 'MY': 5, 'JN': 6,
    'JL': 7, 'AU': 8, 'SE': 9, 'OC': 10, 'NO': 11, 'DE': 12
}

num_to_month_abbr = {v: k for k, v in month_abbr_num.items()}


month_abbr_txt = {
    'JA': '01', 'FE': '02', 'MR': '03', 'AP': '04', 'MY': '05', 'JN': '06',
    'JL': '07', 'AU': '08', 'SE': '09', 'OC': '10', 'NO': '11', 'DE': '12'
}
AZURE_KEY = "628fKIEshyzMxKZKxlKvxNsRtt5ZPqouq3NhDgm8ng8cOaWRPR7MJQQJ99BEACYeBjFXJ3w3AAAFACOGjWD4"
ENDPOINT_URL = (
    "https://scanned-image-text-ocr.cognitiveservices.azure.com/"
    "computervision/imageanalysis:analyze"
    "?features=caption,read"
    "&model-version=latest"
    "&language=en"
    "&api-version=2024-02-01"
)
visuffix = ""

root = tk.Tk()
root.title('Satellite Image Scanner')
root.geometry("700x150")

title_label = tk.Label(root, text="Input Image Data:", anchor=tk.CENTER, font=("Arial", 10), fg="black")
title_label.pack(pady=10)

input_frame = tk.Frame(root)
input_frame.pack(pady=10)

time_label = tk.Label(input_frame, text="Time:")
time_label.grid(row=0, column=0, padx=5, pady=5)
time_entry = tk.Entry(input_frame)
time_entry.grid(row=0, column=1, padx=5, pady=5)

date_label = tk.Label(input_frame, text="Date:")
date_label.grid(row=0, column=2, padx=5, pady=5)
date_entry = tk.Entry(input_frame)
date_entry.grid(row=0, column=3, padx=5, pady=5)

satellite_label = tk.Label(input_frame, text="Satellite:")
satellite_label.grid(row=0, column=4, padx=5, pady=5)
satellite_entry = tk.Entry(input_frame)
satellite_entry.grid(row=0, column=5, padx=5, pady=5)


def button_press():
    """
    Processes the current image, then intelligently finds its place in the
    sequence to determine and populate the next step.
    """
    base_sat_id = satellite_entry.get().strip().split('-')[0]

    vals = process_image()

    if vals:
        # Get the final, corrected values from the scan that just finished
        corrected_sat_text = vals[0]
        corrected_time_text = vals[2]  # e.g., "1400"

        # Determine the band and time that were just processed
        time_just_scanned = f"{corrected_time_text[:2]}:{corrected_time_text[2:]}"
        band_type_just_scanned = ''
        if corrected_sat_text.endswith("-A-2"):
            band_type_just_scanned = 'VIS'
        elif corrected_sat_text.endswith("-A"):
            band_type_just_scanned = 'IR'

        # Find the position of the completed scan in the sequence
        try:
            step_just_completed = (time_just_scanned, band_type_just_scanned)
            current_index = SCAN_SEQUENCE.index(step_just_completed)
            next_scan_index = current_index + 1
        except ValueError:
            print(f"--- WARNING: Scanned item '{step_just_completed}' not in sequence. Automation paused. ---")
            return

        # Check if we've completed the full sequence
        if next_scan_index >= len(SCAN_SEQUENCE):
            next_scan_index = 0  # Reset to the beginning of the scan sequence
            try:
                # Get the current date string from the entry widget
                current_date_str = date_entry.get()
                if not current_date_str:
                    # If the field is empty, do nothing
                    return

                # Parse the 'doy:yy' string into a datetime object
                parsed_date = parse_date(current_date_str)

                # Add one day to the date
                next_day_obj = parsed_date['datetime'] + timedelta(days=1)

                # Format the new date back into 'doy:yy' format (e.g., "182:25")
                new_date_str = f"{next_day_obj.strftime('%j')}:{next_day_obj.strftime('%y')}"

                # Update the date entry with the next day's date
                date_entry.delete(0, tk.END)
                date_entry.insert(0, new_date_str)

            except Exception as e:
                # As a fallback, clear the field if parsing or incrementing fails
                print(f"Could not auto-increment date: {e}")
                date_entry.delete(0, tk.END)

        # Get the next time and band type from the sequence
        next_time, next_band_type = SCAN_SEQUENCE[next_scan_index]

        # Determine the correct satellite suffix based on the band type
        if next_band_type == 'IR':
            next_sat_text = f"{base_sat_id}-A"
        else:  # 'VIS'
            next_sat_text = f"{base_sat_id}-A-2"

        # Update the GUI with the values for the next scan
        time_entry.delete(0, tk.END)
        time_entry.insert(0, next_time)

        satellite_entry.delete(0, tk.END)
        satellite_entry.insert(0, next_sat_text)

    return


def convert_doy_to_ddmmyy(doy_yy_str):
    try:
        doy_str, year_str = doy_yy_str.split(':')
        doy = int(doy_str)
        year_suffix = int(year_str)
        if doy > 366 or doy < 1:
            print("Day of year is out of range.")
            return doy_yy_str
        full_year = 1900 + year_suffix if year_suffix >= 50 else 2000 + year_suffix
        date_obj = datetime(full_year, 1, 1) + timedelta(days=doy - 1)
        day = date_obj.strftime('%d')
        month_map_rev = {
            1: 'JA', 2: 'FE', 3: 'MR', 4: 'AP', 5: 'MY', 6: 'JN',
            7: 'JL', 8: 'AU', 9: 'SE', 10: 'OC', 11: 'NO', 12: 'DE'
        }
        month_code = month_map_rev[date_obj.month]
        return f"{day}{month_code}{year_suffix:02d}"
    except (ValueError, KeyError) as e:
        print(f"Error converting DOY:YY date: {e}")
        return doy_yy_str


def process_image():
    result = subprocess.run(
        ["epsonscan2", "--scan", "./quickscan.sf2"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
    )
    if result.returncode == 0:
        match = re.search(r'imageCount:(\d+)', result.stdout)
        if match:
            image_title = "img" + match.group(1)
            print(f"Extracted: {image_title}")
        else:
            print("Couldn't find image count in output.")
            return
    else:
        print(f"Command failed with code {result.returncode}\nError: {result.stderr}")
        return

    time_text = time_entry.get().strip()
    date_text = date_entry.get().strip()
    satellite_text = satellite_entry.get().strip()

    if not all([image_title, time_text, date_text, satellite_text]):
        print("All fields must be filled!")
        return []

    for file in os.listdir("images"):
        if file.startswith(image_title):
            corrected_vals = check_against_ocr(file, satellite_text, date_text, time_text)
            close_all_toplevels(root)

            corrected_sat_text, corrected_date_text, corrected_time_text = corrected_vals[:3]

            final_date_text = corrected_date_text
            if ":" in corrected_date_text and len(corrected_date_text.split(':')) == 2:
                final_date_text = convert_doy_to_ddmmyy(corrected_date_text)

            band, sat_id = "", ""
            if corrected_sat_text.endswith("-A-2"):
                band, sat_id = 'vi', corrected_sat_text.split('-')[0]
            elif corrected_sat_text.endswith("-A"):
                band, sat_id = 'ir', corrected_sat_text.split('-')[0]
            elif len(corrected_sat_text) > 4 and corrected_sat_text[3:5] in ("-2", "-4"):
                band, sat_id = 'vi', corrected_sat_text[:3]
            elif len(corrected_sat_text) > 4 and corrected_sat_text[3:5] == "-Z":
                band, sat_id = 'ir', corrected_sat_text[:3]
            else:
                print(f"Error: Unrecognized satellite format in '{corrected_sat_text}'")
                return []

            year = "19" + final_date_text[4:]
            ddd = parse_ddd(final_date_text)
            month = final_date_text[2:4]
            file_extension = os.path.splitext(file)[1]

            new_filename = f"{sat_id}.{year}.{ddd}.{corrected_time_text}00.{band}{file_extension}"
            json_filename = f"{sat_id}.{year}.{ddd}.{corrected_time_text}00.{band}.json"
            sat_folder = os.path.join(out_base_path, sat_id)
            year_folder = os.path.join(sat_folder, "vissr", year)

            date_folder_string = f"{year}_{month_abbr_txt.get(month)}_{final_date_text[0:2]}_{ddd}"
            date_folder = os.path.join(year_folder, date_folder_string)

            os.makedirs(date_folder, exist_ok=True)
            new_path = os.path.join(date_folder, new_filename)
            json_path = os.path.join(date_folder, json_filename)

            scan_profile = "./viscan.sf2" if band == 'vi' else "./irscan.sf2"
            scan_result = subprocess.run(
                ["epsonscan2", "--scan", scan_profile],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
            )
            if scan_result.returncode == 0:
                src = os.path.join(os.getcwd(), "fullimage", "img.tiff")
                shutil.copy(src, new_path)
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(corrected_vals[3], f, indent=2, ensure_ascii=False)
                if os.path.exists(src):
                    os.remove(src)
                print(f"File copied and renamed to: {date_folder}/{new_filename}")
                return corrected_vals
            else:
                print(f"Scan failed with code {scan_result.returncode}\nError: {scan_result.stderr}")

    print("File not found!")
    return []


def check_against_ocr(file, satellite_text, date_text, time_text):
    img_path = os.path.join(os.getcwd(), "images", file)
    cmd = [
        "curl", "-H", f"Ocp-Apim-Subscription-Key: {AZURE_KEY}",
        "-H", "Content-Type: application/octet-stream",
        "--data-binary", f"@{img_path}", ENDPOINT_URL
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=True)

    azure_output = json.loads(result.stdout)
    vals = get_first_line_text(azure_output).split()
    if len(vals) < 2:
        vals.extend(get_second_line_text(azure_output).split())
    print(f"OCR Values: {vals}")

    if time_text not in vals:
        time_text = open_problem_window(time_text, ' '.join(vals), "Time")

    date_found = False
    if ":" in date_text:
        if date_text in vals:
            date_found = True
    else:
        if date_text in vals or (date_text[:2] + "0" + date_text[3:]) in vals:
            date_found = True

    if not date_found:
        date_text = open_problem_window(date_text, ' '.join(vals), "Date")

    if satellite_text not in vals:
        satellite_text = open_problem_window(satellite_text, ' '.join(vals), "Satellite")

    return [satellite_text, date_text, time_text.replace(":", ""), azure_output]


def get_first_line_text(analyze_result):
    try:
        return analyze_result["readResult"]["blocks"][0]["lines"][0]["text"]
    except (KeyError, IndexError):
        return ''


def get_second_line_text(analyze_result):
    try:
        return analyze_result["readResult"]["blocks"][0]["lines"][1]["text"]
    except (KeyError, IndexError):
        return ''


def open_problem_window(user_text, ocr_text, field_name):
    problem_window = tk.Toplevel(root)
    problem_window.title(f"{field_name} OCR Error")
    problem_window.geometry("400x200")
    problem_window.grab_set()

    tk.Label(problem_window, text=f"OCR Mismatch for {field_name}:", font=("Arial", 12, "bold")).pack(pady=5)
    tk.Label(problem_window, text=f"OCR detected: {ocr_text}", font=("Arial", 10)).pack(pady=5)
    tk.Label(problem_window, text="Your input:", font=("Arial", 10)).pack(pady=5)

    fix_entry = tk.Entry(problem_window, font=("Arial", 10))
    fix_entry.pack(pady=5)
    fix_entry.insert(0, user_text)

    result = {}

    def confirm_correction():
        result['text'] = fix_entry.get()
        problem_window.destroy()

    def accept_ocr():
        result['text'] = ocr_text
        problem_window.destroy()

    btn_frame = tk.Frame(problem_window)
    btn_frame.pack(pady=10)
    tk.Button(btn_frame, text="Confirm My Input", command=confirm_correction).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Accept OCR", command=accept_ocr).pack(side="left", padx=5)

    problem_window.wait_window()
    return result.get('text', user_text)


def parse_ddd(date):
    month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    day = int(date[:2])
    month_code = date[2:4]
    year_suffix = int(date[4:])
    year = 1900 + year_suffix if year_suffix >= 50 else 2000 + year_suffix

    is_leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    if is_leap:
        month_days[1] = 29

    month_index = month_abbr_num.get(month_code)
    if not month_index:
        raise ValueError(f"Invalid month code: {month_code}")

    total_days = sum(month_days[:month_index - 1]) + day
    return f"{total_days:03d}"


def parse_date(date_str):
    """
    Parses date strings in either 'doy:yy' or 'ddMMyy' format.
    Returns a dictionary with various date components.
    """
    date_str = date_str.strip()

    if ':' in date_str:  # Format is 'doy:yy' (e.g., 024:75)
        doy_str, yy_str = date_str.split(':')
        year = 1900 + int(yy_str)
        doy = int(doy_str)
        dt_obj = datetime(year, 1, 1) + timedelta(days=doy - 1)
    else:  # Format is 'ddMMyy' (e.g., 24JA75)
        day = int(date_str[:2])
        month_abbr = date_str[2:4].upper()
        year_suffix = int(date_str[4:])
        year = 1900 + year_suffix
        month = month_abbr_num[month_abbr]
        dt_obj = datetime(year, month, day)

    return {
        'datetime': dt_obj,
        'doy': dt_obj.strftime('%j'),
        'year': str(dt_obj.year),
        'month_abbr': num_to_month_abbr[dt_obj.month],
        'day': dt_obj.strftime('%d'),
        'yy': dt_obj.strftime('%y')
    }


def close_all_toplevels(root):
    for w in root.winfo_children():
        if isinstance(w, tk.Toplevel):
            w.destroy()


# Initialize GUI with the first step of the sequence
initial_time, initial_band = SCAN_SEQUENCE[0]
time_entry.insert(0, initial_time)
satellite_entry.insert(0, '11-A')

submit_button = tk.Button(root, text="Submit", command=button_press)
submit_button.pack(pady=10)

root.mainloop()