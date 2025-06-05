import tkinter as tk
from PIL import Image, ImageTk
import os

# Create the main application window
root = tk.Tk()
root.title("Image Text Labeler")

# Set a maximum size for the window to ensure images fit properly
MAX_WIDTH = 800
MAX_HEIGHT = 600

# Prevent the window from resizing
root.resizable(False, False)

# Label to show image
img_label = tk.Label(root)
img_label.pack()

# Entry to type text
entry = tk.Entry(root, width=80)
entry.pack(pady=10)

# Button to go to next image (hidden but still there for the logic)
button = tk.Button(root, text="Save and Next")
button.pack(pady=5)

# Index to keep track of images
image_index = 8
max_index = 25  # inclusive

def resize_image(img):
    # Resize image to fit within max width and height while maintaining the aspect ratio
    width, height = img.size
    aspect_ratio = width / height
    if width > MAX_WIDTH or height > MAX_HEIGHT:
        if width / MAX_WIDTH > height / MAX_HEIGHT:
            new_width = MAX_WIDTH
            new_height = int(MAX_WIDTH / aspect_ratio)
        else:
            new_height = MAX_HEIGHT
            new_width = int(MAX_HEIGHT * aspect_ratio)
        img = img.resize((new_width, new_height))
    return img

def process_next():
    global image_index

    if image_index > max_index:
        root.quit()
        return

    # Load and crop the image
    image_path = rf"images\test{image_index}.tif"
    img = Image.open(image_path)
    width, height = img.size
    img_text = img.crop((0, 0, width, height / 15))

    # Resize the cropped image to fit the screen
    img_text_resized = resize_image(img_text)

    # Convert to format Tkinter can display
    img_tk = ImageTk.PhotoImage(img_text_resized)
    img_label.img = img_tk  # keep a reference!
    img_label.config(image=img_tk)

    # Clear the entry field
    entry.delete(0, tk.END)

def save_and_next(event=None):
    global image_index

    # Get the typed text
    text = entry.get()

    if not text.strip():
        return  # Skip if nothing typed

    # Reopen and crop to get the actual image to save
    image_path = rf"images\test{image_index}.tif"
    img = Image.open(image_path)
    width, height = img.size
    img_text = img.crop((0, height / 20, width, height / 10))

    # Save the cropped image and the corresponding text
    base_path = r"C:\Users\lokii\Documents\trainingdata"
    img_text.save(os.path.join(base_path, f"eng_pixelfont.exp{image_index-1}.tif"))

    with open(os.path.join(base_path, f"eng_pixelfont.exp{image_index-1}.gt.txt"), "w", encoding="utf-8") as f:
        f.write(text)

    image_index += 1
    process_next()

# Bind the Enter key to auto-advance
root.bind("<Return>", save_and_next)

# Start with the first image
process_next()

# Start the GUI event loop
root.mainloop()
