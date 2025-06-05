import cv2
import PIL
from PIL import Image, UnidentifiedImageError
import os
import imagehash
from skimage.metrics import structural_similarity as ssim
import numpy as np
import math


PIL.Image.MAX_IMAGE_PIXELS = 408040001
search_directory = "dpitest01FE86IR"
compare_img_dpi = "2000"
compare_img = f"{compare_img_dpi}.tiff"
ref_img   = Image.open(os.path.join(search_directory, compare_img))
pairs_file = os.path.join(search_directory, f"{search_directory}{compare_img_dpi}pairs.txt")

def hashCompare(img):
    hash0 = imagehash.average_hash(img,hash_size=64)
    hash1 = imagehash.average_hash(ref_img,hash_size=64)
    return hash0 - hash1

#takes too long
def ssim_score(img):
    # load and convert to grayscale arrays
    imgA = np.array(img.convert("L"))
    imgB = np.array(ref_img.convert("L"))
    score, _ = ssim(imgA, imgB, full=True)
    return score  # in [-1, 1], with 1.0 = identical

def mse(img):
    a = np.array(img.convert("L"), dtype=np.float32)
    b = np.array(ref_img.convert("L"), dtype=np.float32)
    return np.mean((a - b) ** 2)

def psnr(m):
    if m == 0:
        return float("inf")
    PIXEL_MAX = 255.0
    return 20 * math.log10(PIXEL_MAX / math.sqrt(m))

hash_pairs = []
hash_vals = []
mse_pairs = []
mse_vals = []
psnr_pairs = []
psnr_vals = []
for file in os.listdir(search_directory):
    try:
        img = Image.open(os.path.join(os.getcwd(), search_directory, file))
    except (UnidentifiedImageError, OSError):
        continue
    img = img.resize(ref_img.size, resample=Image.LANCZOS)
    #img.save(os.path.join(r"C:\Users\lokii\PycharmProjects\PythonProject\.venv\Scripts\resizedtestimages\\", file))
    print(file)
    hash = hashCompare(img)
    print(f"hash compare at 64: {hash}")
    #print(f"ssim compare: {ssim_score(img)}")
    mse_val = mse(img)
    print(f"mse compare: {mse_val}")
    psnr_val = psnr(mse_val)
    print(f"psnr compare: {psnr_val}")
    filename = file.replace(".tiff","")
    hash_pairs.append(f"({filename},{hash})")
    hash_vals.append(hash)
    mse_pairs.append(f"({filename},{mse_val})")
    mse_vals.append(mse_val)
    psnr_pairs.append(f"({filename},{psnr_val})")
    psnr_vals.append(psnr_val)


print(hash_pairs)
print(mse_pairs)
print(psnr_pairs)
print(hash_vals)
print(mse_vals)
print(psnr_vals)

with open(pairs_file, "a") as f:
    f.write("hash pairs: " + ", ".join(map(str, hash_pairs)) + "\n")
    f.write("mse pairs: "  + ", ".join(map(str, mse_pairs))  + "\n")
    f.write("psnr pairs: " + ", ".join(map(str, psnr_pairs)) + "\n")
    f.write("hash vals: "  + ", ".join(map(str, hash_vals))  + "\n")
    f.write("mse vals: "   + ", ".join(map(str, mse_vals))   + "\n")
    f.write("psnr vals: "  + ", ".join(map(str, psnr_vals))  + "\n")

with open(pairs_file, "a") as f:
    f.write("hash pairs: " + str(hash_pairs) + "\n")
    f.write("mse pairs: "  + str(mse_pairs)  + "\n")
    f.write("psnr pairs: " + str(psnr_pairs) + "\n")
    f.write("hash vals: "  + str(hash_vals)  + "\n")
    f.write("mse vals: "   + str(mse_vals)   + "\n")
    f.write("psnr vals: "  + str(psnr_vals)  + "\n")