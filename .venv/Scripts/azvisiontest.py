from azvision import scan

img = r'C:\Users\lokii\PycharmProjects\PythonProject\.venv\Scripts\images\test2.tif'
VISION_KEY = '628fKIEshyzMxKZKxlKvxNsRtt5ZPqouq3NhDgm8ng8cOaWRPR7MJQQJ99BEACYeBjFXJ3w3AAAFACOGjWD4'
VISION_ENDPOINT = r'https://scanned-image-text-ocr.cognitiveservices.azure.com/'
resp = scan(img, key=VISION_KEY, endpoint=VISION_ENDPOINT)

# prints text in image
print(resp.readResult.content)
