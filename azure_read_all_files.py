import json
import subprocess
import os
import time

AZURE_KEY    = "628fKIEshyzMxKZKxlKvxNsRtt5ZPqouq3NhDgm8ng8cOaWRPR7MJQQJ99BEACYeBjFXJ3w3AAAFACOGjWD4"
ENDPOINT_URL = (
    "https://scanned-image-text-ocr.cognitiveservices.azure.com/"
    "computervision/imageanalysis:analyze"
    "?features=caption,read"
    "&model-version=latest"
    "&language=en"
    "&api-version=2024-02-01"
)
BASE_DIR = r"/data1/oper/robo/nasa/film/goes1/NA/"
SAVE_DIR = r"/home/sgunshor/filmgoes1NAazure"
os.makedirs(SAVE_DIR, exist_ok=True)


for file in os.listdir(BASE_DIR):
    name = file
    while name.lower().endswith(".jpg"):
        name = name[:-4]
    json_name = name + ".json"
    json_path = os.path.join(SAVE_DIR, json_name)
    if os.path.exists(json_path):
        continue

    img_path = os.path.join(BASE_DIR, file)
    cmd = [
            "curl",
            "-H", f"Ocp-Apim-Subscription-Key: {AZURE_KEY}",
            "-H", "Content-Type: application/octet-stream",
            "--data-binary", f"@{img_path}",  # use the full path, with @
            ENDPOINT_URL  # no extra quotes here
        ]
    print(cmd)
    # run the process, capture stdout/stderr, return text
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        check=True
    )

    azure_output = json.loads(result.stdout)
    print(file)
    print(azure_output)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(azure_output, f, indent=2, ensure_ascii=False)

    time.sleep(9)
