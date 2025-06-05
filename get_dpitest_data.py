import subprocess
import re
import time
import os
import shutil

dpis = [100,200,300,400,500,600,700,800,900,1000,1100,1200,1800,2000]


folder_name = input("What should the folder be called?\n")
folder_path = os.path.join(os.getcwd(), folder_name)
os.makedirs(folder_path)
times_file = os.path.join(folder_path, "dpitimes.txt")


for dpi in dpis:
    start_time = time.time()

    result = subprocess.run(
        [
            "epsonscan2",
            "--scan",
            f"./dpisfs/{dpi}.sf2"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,  # returns str instead of bytes
    )

    if result.returncode == 0:
        new_path = os.path.join(folder_path, f"{dpi}.tiff")
        image_dir = os.path.join(os.getcwd(), "dpitempimg")
        src = os.path.join(image_dir, f"{dpi}.tiff")
        shutil.copy(src, new_path)
        if os.path.exists(src):
            os.remove(src)

        end_time = time.time()

        elapsed_time = end_time - start_time
        time_message = f"{dpi} - {elapsed_time:.0f} seconds\n"
        print(time_message, end="")
        with open(times_file, "a") as f:
            f.write(time_message)

    else:
        print(f"Command failed with code {result.returncode}")
        print("Error output:", result.stderr)