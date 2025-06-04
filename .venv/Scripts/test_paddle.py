from paddleocr import PaddleOCR
ocr = PaddleOCR()


img = Image.open(r"images\test4.tif")
width, height = img.size
img_text = img.crop((0,height/20,width,height/12))
img_text.show()



result = ocr.ocr(img_text)
print(result)