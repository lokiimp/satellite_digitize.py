import cv2
from PIL import Image
from pytesseract import pytesseract
import numpy as np




# Defining paths to tesseract.exe and the image we would be using
path_to_tesseract = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
pytesseract.tesseract_cmd = path_to_tesseract

# Set the config for custom traineddata file

image_path = r"images\test2.tif"

# Opening the image & storing it in an image object
img = Image.open(image_path)

# Create a crop of the image for the text
width, height = img.size
img_text = img.crop((0, height / 20, width, height / 10))
img_text.show()


img = cv2.imread(r"images\test2.tif")
gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]




# Loop through different PSM modes and extract text
for i in range(8, 11):
    print(pytesseract.image_to_string(img_text, config=f'--oem 1 --psm {i}'))
    #print(pytesseract.image_to_string(thresh, lang='eng', config=f'--psm {i}'))
