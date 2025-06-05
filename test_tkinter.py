import tkinter as tk
import shutil
import os
from datetime import datetime, timedelta

root = tk.Tk()
root.title('Test Autofill Program')
root.geometry("600x250")

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

# Image Path input
image_path_label = tk.Label(root, text="Image Title (temp):")
image_path_label.pack(pady=5)
image_path_entry = tk.Entry(root, width=50)
image_path_entry.pack(pady=5)


def button_press():
    process_image()
    time_entry.delete(0, tk.END)

    satellite_text = satellite_entry.get().strip()
    if satellite_text == "32A-2":
        satellite_entry.delete(0, tk.END)
        satellite_entry.insert(0, "32A-Z")
    elif satellite_text == "32A-Z":
        satellite_entry.delete(0, tk.END)
        satellite_entry.insert(0, "32A-2")
        #only update date if it's the second satellite
        date_text = date_entry.get().strip()
        date_text = increment_date(date_text)
        date_entry.delete(0, tk.END)
        date_entry.insert(0, date_text)
    else:
        satellite_entry.delete(0, tk.END)
    image_path_entry.delete(0, tk.END)
    return

# Function to handle file renaming
def process_image():
    #print("Current Working Directory:", os.getcwd())
    image_title = image_path_entry.get().strip()
    time_text = time_entry.get().strip()
    date_text = date_entry.get().strip()
    satellite_text = satellite_entry.get().strip()

    if not image_title or not time_text or not date_text or not satellite_text:
        print("All fields must be filled!")
        return

    # Search for file in current directory
    for file in os.listdir():
        if file.startswith(image_title):
            file_extension = os.path.splitext(file)[1]
            new_filename = f"{satellite_text}{date_text}{time_text}{file_extension}"
            new_path = os.path.join(os.getcwd(), new_filename)
            shutil.copy(file, new_path)
            print(f"File copied and renamed to: {new_filename}")
            return

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
# Submit Button
submit_button = tk.Button(root, text="Submit", command=button_press)
submit_button.pack(pady=10)

root.mainloop()
