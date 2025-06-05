import tkinter as tk
import shutil
import os
from datetime import datetime, timedelta
from PIL import Image, ImageTk
from pytesseract import pytesseract
import subprocess
import re

TEST = False
SETUP = True

month_abbr_num = {
        'JA': 1, 'FE': 2, 'MR': 3, 'AP': 4, 'MY': 5, 'JN': 6,
        'JL': 7, 'AU': 8, 'SE': 9, 'OC': 10, 'NO': 11, 'DE': 12
    }

month_abbr_txt = {
        'JA': '01', 'FE': '02', 'MR': '03', 'AP': '04', 'MY': '05', 'JN': '06',
        'JL': '07', 'AU': '08', 'SE': '09', 'OC': '10', 'NO': '11', 'DE': '12'
    }

#path_to_tesseract = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
path_to_tesseract = r"/usr/bin/tesseract"
pytesseract.tesseract_cmd = path_to_tesseract

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
    #print("Current Working Directory:", os.getcwd())
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
            band = corrected_vals[0][4:5]
            file_extension = os.path.splitext(file)[1]
            new_filename = f"{satellite_text}.{year}.{ddd}.{time_text}00.{band}{file_extension}"
            year_folder = os.path.join(os.getcwd(), year)
            date_folder_string = f"{year}_{month_abbr_txt.get(date_text[2:4])}_{date_text[0:2]}_{ddd}"
            date_folder = os.path.join(year, date_folder_string)
            if not os.path.exists(year_folder):
                os.makedirs(year_folder)
            if not os.path.exists(date_folder):
                os.makedirs(date_folder)
            new_path = os.path.join(date_folder, new_filename)
            image_dir = os.path.join(os.getcwd(), "images")
            shutil.copy(os.path.join(image_dir, file), new_path)
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
    img = Image.open(os.path.join(os.getcwd(), "images", file))
    width, height = img.size
    # TODO fixing this will make OCR run way better
    img_text = img.crop((0, 0, width, height / 15))
    if TEST:
        img_text.show()
        for i in range(3, 13):
            print(i)
            print(pytesseract.image_to_string(img_text, lang="eng_pixelfont_v2.1", config=f'--oem 1 --psm {i}'))

    #print(pytesseract.tesseract_cmd)
    vals = pytesseract.image_to_string(img_text, lang="eng_pixelfont_v2.1", config=f'--oem 1 --psm 8').split()
    print(vals)

    if SETUP:
        any_error = False;
        if time_text not in vals:
            time_index = -1  # default if not found
        else:
            time_index = vals.index(time_text)
        if time_index == -1:
            full_text = open_problem_window_setup(img_text)
            any_error = True;
        else:
            if date_text not in vals and not any_error:
                full_text = open_problem_window_setup(img_text)
                any_error = True;
            if satellite_text not in vals and not any_error:
                full_text = open_problem_window_setup(img_text)
                any_error = True;
        if any_error:
            vals = full_text.split()
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
    return [satellite_text, date_text, time_text]


def open_problem_window(user_text, ocr_text):
    problem_window = tk.Toplevel()
    problem_window.title("OCR Error")
    problem_window.geometry("400x200")  # Adjusted for better size
    problem_window.update_idletasks()  # Ensures correct dimensions
    x = root.winfo_x() + (root.winfo_width() // 2) - (problem_window.winfo_width() // 2)
    y = root.winfo_y() + (root.winfo_height() // 2) - (problem_window.winfo_height() // 2)
    problem_window.geometry(f"+{x}+{y}")

    # Make it modal
    problem_window.grab_set()

    tk.Label(problem_window, text="OCR Mismatch:", font=("Arial", 12, "bold")).pack(pady=5)

    tk.Label(problem_window, text=f"OCR detected: {ocr_text}", font=("Arial", 10)).pack(pady=5)

    tk.Label(problem_window, text="Correct value:", font=("Arial", 10)).pack(pady=5)

    fix_entry = tk.Entry(problem_window, font=("Arial", 10))
    fix_entry.pack(pady=5)
    fix_entry.insert(0, user_text)

    def confirm_correction():
        nonlocal user_text
        user_text = fix_entry.get()
        problem_window.destroy()

    button_confirm = tk.Button(problem_window, text="Confirm", command=confirm_correction)
    button_confirm.pack(pady=10)

    problem_window.wait_window()  # Wait until the user closes the window

    return user_text  # Return corrected value

def open_problem_window_setup(pil_img):
    """
    :param pil_img: a PIL.Image instance (cropped from your TIFF)
    :returns: the string the user types in
    """
    # Container for the result
    answer = {"text": None}
    # Create the popup
    popup = tk.Toplevel(root)
    popup.title("OCR Correction")
    popup.grab_set()  # make it modal
    # Figure out max size (e.g. 80% of screen)
    screen_w = popup.winfo_screenwidth()
    screen_h = popup.winfo_screenheight()
    max_w, max_h = int(screen_w * 0.8), int(screen_h * 0.8)
    # Scale image down if too big
    img_w, img_h = pil_img.size
    if img_w > max_w or img_h > max_h:
        pil_img = pil_img.copy()  # avoid mutating original
        pil_img.thumbnail((max_w, max_h), Image.LANCZOS)
    # Convert to PhotoImage and display
    photo = ImageTk.PhotoImage(pil_img)
    img_label = tk.Label(popup, image=photo)
    img_label.image = photo
    img_label.pack(pady=10)
    # Prompt + entry
    tk.Label(popup, text="Please type the text as it appears above:").pack()
    entry = tk.Entry(popup, width=60)
    entry.insert(0, "↑")
    entry.pack(pady=5)
    # On submit, save and close
    def on_submit():
        answer["text"] = entry.get().strip()
        popup.destroy()
    tk.Button(popup, text="Submit", command=on_submit).pack(pady=10)
    # Center and show the window
    popup.update_idletasks()
    w, h = popup.winfo_width(), popup.winfo_height()
    x = (screen_w - w) // 2
    y = (screen_h - h) // 2
    popup.geometry(f"{w}x{h}+{x}+{y}")
    # Wait until user closes
    popup.wait_window()
    folder = "trainingdata"
    os.makedirs(folder, exist_ok=True)
    # find existing exp numbers
    existing = []
    for fname in os.listdir(folder):
        base, ext = os.path.splitext(fname)
        if base.startswith("eng_pixelfont.exp") and ext.lower() in (".tif", ".tiff", ".gt.txt"):
            suffix = base.split("exp", 1)[1]
            if suffix.isdigit():
                existing.append(int(suffix))
    n = 1
    while n in existing:
        n += 1
    # save the image
    img_fname = f"eng_pixelfont.exp{n}.tif"
    pil_img.save(os.path.join(folder, img_fname))
    # save the ground-truth text
    gt_fname = f"eng_pixelfont.exp{n}.gt.txt"
    with open(os.path.join(folder, gt_fname), "w", encoding="utf-8") as f:
        f.write(answer["text"])
    return answer["text"]

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




# Submit Buttont
submit_button = tk.Button(root, text="Submit", command=button_press)
submit_button.pack(pady=10)

root.mainloop()
