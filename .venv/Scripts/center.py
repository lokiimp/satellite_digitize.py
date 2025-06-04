import json
import numpy as np
import cv2 as cv
import os

def print_lines(file):
    azure_output = json.load(file)
    print(azure_output)
    blocks = azure_output["readResult"]["blocks"]
    first_block = blocks[0]
    for ln in first_block["lines"]:
        print(ln["text"])


def find_sms(file):
    azure_output = json.load(file)
    blocks = azure_output["readResult"]["blocks"]
    first_block = blocks[0]
    for ln in first_block["lines"]:
        if ln["text"] in ("SMS-2","SHS-2","SHE-2"):
            return ln["boundingPolygon"][0]

base_path = r"C:\Users\lokii\PycharmProjects\PythonProject\.venv\Scripts\center"
file1 = "32A.1976.243.204500.vi.json"
file2 = "32A.1976.244.204500.vi.json"
image1 = "32A.1976.243.204500.vi.thumb.png"
image2 = "32A.1976.244.204500.vi.thumb.png"

with open(os.path.join(base_path,file1), 'r') as file:
    coords = find_sms(file)
    xshift = 660 - int(coords["x"])
    yshift = 55 - int(coords["y"])
    print(xshift, yshift)
    print(coords)
    img1 = cv.imread(os.path.join(base_path,image1))
    height, width = img1.shape[:2]
    shift_height, shift_width = yshift * (height / 757), xshift * (width / 757)
    T = np.float32([[1, 0, shift_width], [0, 1, shift_height]])
    img1_translation = cv.warpAffine(img1, T, (width, height))
    cv.imwrite(os.path.join(base_path,"shiftimg1.png"), img1_translation)

with open(os.path.join(base_path,file2), 'r') as file:
    coords = find_sms(file)
    xshift = 660 - int(coords["x"])
    yshift = 55 - int(coords["y"])
    print(xshift, yshift)
    print(coords)
    img2 = cv.imread(os.path.join(base_path, image2))
    height, width = img2.shape[:2]
    shift_height, shift_width = yshift * (height / 757), xshift * (width / 757)
    T = np.float32([[1, 0, shift_width], [0, 1, shift_height]])
    img2_translation = cv.warpAffine(img2, T, (width, height))
    cv.imwrite(os.path.join(base_path, "shiftimg2.png"),img2_translation)



