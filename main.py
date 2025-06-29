import os
from tkinter import Tk, Button, Label, filedialog, Listbox, END
from PIL import Image
import imagehash

class DuplicateImageFinder:
    def __init__(self, root):
        self.root = root
        self.root.title("Duplicate Image Finder")

        self.label = Label(root, text="Select a folder to scan for duplicates:")
        self.label.pack(pady=10)

        self.select_button = Button(root, text="Select Folder", command=self.select_folder)
        self.select_button.pack(pady=5)

        self.result_list = Listbox(root, width=100)
        self.result_list.pack(pady=10)

    def select_folder(self):
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.find_duplicates(folder_path)

    def find_duplicates(self, folder_path):
        self.result_list.delete(0, END)
        hashes = {}
        duplicates = []

        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(('png', 'jpg', 'jpeg', 'bmp', 'gif')):
                    path = os.path.join(root, file)
                    try:
                        img = Image.open(path)
                        hash_val = imagehash.phash(img)
                        if hash_val in hashes:
                            duplicates.append((path, hashes[hash_val]))
                        else:
                            hashes[hash_val] = path
                    except Exception as e:
                        self.result_list.insert(END, f"Error: {file} ({str(e)})")

        if duplicates:
            for dup in duplicates:
                self.result_list.insert(END, f"Duplicate Found:\n  {dup[0]}\n  {dup[1]}\n")
        else:
            self.result_list.insert(END, "No duplicates found.")

if __name__ == "__main__":
    root = Tk()
    app = DuplicateImageFinder(root)
    root.mainloop()
