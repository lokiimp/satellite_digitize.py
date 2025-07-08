import tkinter as tk
import shutil
import os
from datetime import datetime, timedelta
import subprocess
import re
import json

TEST = False

out_base_path = "/ships22/sds/goes/digitized"

# UPDATED: New automated workflow sequence
SCAN_SEQUENCE = [
    ('02:00', 'IR'),
    ('08:00', 'IR'),
    ('14:00', 'IR'),
    ('14:00', 'VIS'),
    ('20:00', 'IR'),
    ('20:00', 'VIS'),
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

# --- GUI Setup ---
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
    vals = process_image()

    if vals:
        corrected_sat_text = vals[0]
        corrected_time_text = vals[2]

        base_sat_id = ""
        if corrected_sat_text.endswith("-Z"):
            base_sat_id = corrected_sat_text.replace("-Z", "")
        elif corrected_sat_text.endswith("-2"):
            base_sat_id = corrected_sat_text.replace("-2", "")

        time_just_scanned = f"{corrected_time_text[:2]}:{corrected_time_text[2:]}"
        band_type_just_scanned = ''
        if corrected_sat_text.endswith("-2"):
            band_type_just_scanned = 'VIS'
        elif corrected_sat_text.endswith("-Z"):
            band_type_just_scanned = 'IR'

        try:
            step_just_completed = (time_just_scanned, band_type_just_scanned)
            current_index = SCAN_SEQUENCE.index(step_just_completed)
            next_scan_index = current_index + 1
        except ValueError:
            print(f"--- WARNING: Scanned item '{step_just_completed}' not in sequence. Automation paused. ---")
            return

        # Check if we've completed the full daily sequence
        if next_scan_index >= len(SCAN_SEQUENCE):
            next_scan_index = 0  # Reset to the beginning
            try:
                current_date_str = date_entry.get().strip()
                if not current_date_str: return

                # Parse ddMMyy string to datetime object
                day = int(current_date_str[:2])
                month_abbr = current_date_str[2:4].upper()
                year_suffix = int(current_date_str[4:])
                month = month_abbr_num[month_abbr]
                year = 1900 + year_suffix

                current_dt = datetime(year, month, day)
                next_day_obj = current_dt + timedelta(days=1)

                # Format new date back into ddMMyy string
                new_date_str = f"{next_day_obj.strftime('%d')}{num_to_month_abbr[next_day_obj.month]}{next_day_obj.strftime('%y')}"

                date_entry.delete(0, tk.END)
                date_entry.insert(0, new_date_str)

            except (ValueError, KeyError) as e:
                print(f"Could not auto-increment date: {e}")
                date_entry.delete(0, tk.END)

        next_time, next_band_type = SCAN_SEQUENCE[next_scan_index]

        if next_band_type == 'IR':
            next_sat_text = f"{base_sat_id}-Z"
        else:  # 'VIS'
            next_sat_text = f"{base_sat_id}-2"

        time_entry.delete(0, tk.END)
        time_entry.insert(0, next_time)
        satellite_entry.delete(0, tk.END)
        satellite_entry.insert(0, next_sat_text)

    return


def process_image():
    # This can be enabled when a physical scanner is connected
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

            # Date is now always in ddMMyy format
            final_date_text = corrected_date_text

            band, sat_id = "", ""
            if corrected_sat_text.endswith("-2"):
                band, sat_id = 'vi', corrected_sat_text.replace('-2', '')
            elif corrected_sat_text.endswith("-Z"):
                band, sat_id = 'ir', corrected_sat_text.replace('-Z', '')
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

            # Create directories if they don't exist
            if not TEST and not os.path.exists(date_folder):
                os.makedirs(date_folder, exist_ok=True)

            new_path = os.path.join(date_folder, new_filename)
            json_path = os.path.join(date_folder, json_filename)

            scan_profile = "./viscan.sf2" if band == 'vi' else "./irscan.sf2"
            print(f"File will be copied to: {new_path}")
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
            return corrected_vals

    print("Scanned file not found!")
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
    """
    Calculates the day of the year (ddd) from a ddMMyy string.
    """
    month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    day = int(date[:2])
    month_code = date[2:4].upper()
    year_suffix = int(date[4:])
    year = 1900 + year_suffix

    is_leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    if is_leap:
        month_days[1] = 29

    month_index = month_abbr_num.get(month_code)
    if not month_index:
        raise ValueError(f"Invalid month code: {month_code}")

    total_days = sum(month_days[:month_index - 1]) + day
    return f"{total_days:03d}"


def close_all_toplevels(root_win):
    for w in root_win.winfo_children():
        if isinstance(w, tk.Toplevel):
            w.destroy()


# --- Main Execution ---

# Initialize GUI with the first step of the sequence
initial_time, initial_band = SCAN_SEQUENCE[0]
time_entry.insert(0, initial_time)
# UPDATED: Set initial satellite to the new IR format
satellite_entry.insert(0, '11A-Z')

submit_button = tk.Button(root, text="Submit & Process", command=button_press)
submit_button.pack(pady=10)

root.mainloop()