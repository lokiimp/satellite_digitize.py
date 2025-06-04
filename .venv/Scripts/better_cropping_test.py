from PIL import Image
import cv2
import numpy as np
import pytesseract

def auto_crop_text_region(pil_img):
    # Convert PIL image to OpenCV format
    img = np.array(pil_img.convert('RGB'))
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    # Apply threshold to get binary image
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Find contours (white blobs on black background)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Filter out small contours and get bounding boxes
    bounding_boxes = [cv2.boundingRect(c) for c in contours if cv2.contourArea(c) > 100]

    if not bounding_boxes:
        return pil_img  # fallback to original if no contours

    # Get bounding box that contains all other boxes
    x_min = min([x for (x, y, w, h) in bounding_boxes])
    y_min = min([y for (x, y, w, h) in bounding_boxes])
    x_max = max([x + w for (x, y, w, h) in bounding_boxes])
    y_max = max([y + h for (x, y, w, h) in bounding_boxes])

    # Add a bit of padding
    pad = 5
    x_min = max(0, x_min - pad)
    y_min = max(0, y_min - pad)
    x_max = min(img.shape[1], x_max + pad)
    y_max = min(img.shape[0], y_max + pad)

    # Crop and return as PIL Image
    cropped = img[y_min:y_max, x_min:x_max]
    return Image.fromarray(cropped)


image = Image.open(r"C:\Users\lokii\PycharmProjects\PythonProject\.venv\Scripts\images\test2.tif")
cropped = auto_crop_text_region(image)
cropped.show()
path_to_tesseract = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
pytesseract.tesseract_cmd = path_to_tesseract
text = pytesseract.image_to_string(cropped, config="--oem 1 --psm 8", lang="eng_pixelfont_v2.1")
print(text)