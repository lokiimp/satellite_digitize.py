import json
import re
import os

SEARCH_DIR = r"/home/sgunshor/filmgoes1NAazure"
IMAGE_DIR = r"/data1/oper/robo/nasa/film/goes1/NA/"

search_term = input("search term: ").strip()
pattern     = re.compile(re.escape(search_term), re.IGNORECASE)
found = False

for file in os.listdir(SEARCH_DIR):
    if not file.lower().endswith(".json"):
        continue

    with open(os.path.join(SEARCH_DIR, file), 'r', errors='ignore') as f:
        data = json.load(f)

    texts = []
    cap = data.get("captionResult", {})
    if isinstance(cap.get("text"), str):
        texts.append(cap["text"])

    for block in data.get("readResult", {}).get("blocks", []):
        for line in block.get("lines", []):
            if isinstance(line.get("text"), str):
                texts.append(line["text"])

    for snippet in texts:
        if pattern.search(snippet):
            print(search_term, " exists in ", file)
            img_name = file.replace(".json", ".jpg")
            if os.path.exists(os.path.join(IMAGE_DIR, img_name)):
                print(f"https://dcarchivex.ssec.wisc.edu/robo/nasa/film/goes1/NA/{img_name}")
            else:
                img_name = file.replace(".json", ".jpg.jpg")
                if os.path.exists(os.path.join(IMAGE_DIR, img_name)):
                    print(f"https://dcarchivex.ssec.wisc.edu/robo/nasa/film/goes1/NA/{img_name}")
                else:
                    print("image not found")
            found = True
if not found:
    print("No instances found.")
