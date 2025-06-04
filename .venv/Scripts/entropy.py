import PIL
from PIL import Image
import os


PIL.Image.MAX_IMAGE_PIXELS = 408040001
for file in os.listdir("dpitest"):
    img = Image.open(os.path.join(os.getcwd(), "dpitest", file))
    img.resize([20200,20200])
    print(file)
    print(img.entropy())