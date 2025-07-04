import os
from tkinter import (
    Tk, Button, Label, filedialog, Listbox, END,
    Checkbutton, BooleanVar, Toplevel, messagebox,
    Canvas, Frame, Scrollbar
)
from PIL import Image, ImageTk
import imagehash
import shutil

class DuplicateImageFinder:
    def __init__(self, root):

        self.duplicate_pairs = []
        self.deletion_vars = []
        self.deletion_paths = []

        self.root = root
        self.root.title("Duplicate Image Finder")

        self.label = Label(root, text="Select a folder to scan for duplicates:")
        self.label.pack(pady=10)

        self.select_button = Button(root, text="Select Folder", command=self.select_folder)
        self.select_button.pack(pady=5)

        # Log checkbox
        self.log_var = BooleanVar(value=False)
        self.log_checkbox = Checkbutton(
            root,
            text="Create log file of duplicates",
            variable=self.log_var
        )
        self.log_checkbox.pack(pady=5)

        # Listbox w/ scroll bars
        list_frame = Frame(self.root)
        list_frame.pack(expand=True, fill="both", padx=10, pady=10)

        self.v_scroll = Scrollbar(list_frame, orient="vertical")
        self.v_scroll.pack(side="right", fill="y")

        self.h_scroll = Scrollbar(list_frame, orient="horizontal")
        self.h_scroll.pack(side="bottom", fill="x")

        self.result_list = Listbox(
            list_frame,
            width=150,
            yscrollcommand=self.v_scroll.set,
            xscrollcommand=self.h_scroll.set
        )
        self.result_list.pack(side="left", expand=True, fill="both")

        self.v_scroll.config(command=self.result_list.yview)
        self.h_scroll.config(command=self.result_list.xview)

        # Thumbnail preview
        self.preview_button = Button(root, text="Preview Thumbnails", command=self.show_preview_window)
        self.preview_button.pack(pady=5)
        self.preview_button.config(state='disabled')

        # Trash handling w/ undo
        self.trash_dir = os.path.join(os.getcwd(), ".trash")
        os.makedirs(self.trash_dir, exist_ok=True)
        self.last_deleted = []
        self.undo_button = Button(
            root,
            text="Undo Last Delete",
            command=self._undo_delete
        )
        self.undo_button.pack(pady=5)
        self.undo_button.config(state="disabled")

        # Trash handling w/ "empty trash" (permanent delete)
        self.empty_button = Button(
            root,
            text="Empty Trash",
            command=self._empty_trash
        )
        self.empty_button.pack(pady=5)


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

        self.duplicate_pairs = duplicates

        if duplicates:
            self.preview_button.config(state='normal')
        else:
            self.preview_button.config(state='disabled')

        if duplicates and self.log_var.get():
            log_file = os.path.join(os.getcwd(), 'duplicate_log.txt')
            try:
                with open(log_file, 'w') as f:
                    f.write('Duplicate pairs found:\n')
                    for dup in duplicates:
                        f.write(f"{dup[0]}, {dup[1]}\n")
                self.result_list.insert(END, f"Log file created at {log_file}")
            except Exception as e:
                self.result_list.insert(END, f"Error writing log file: {e}")

        if duplicates:
            for dup in duplicates:
                self.result_list.insert(END, f"Duplicate Found:\n  {dup[0]}\n  {dup[1]}\n")
        else:
            self.result_list.insert(END, "No duplicates found.")


    def show_preview_window(self):
        if not self.duplicate_pairs:
            return

        preview = Toplevel(self.root)
        preview.title("Select Duplicates to Delete")

        control_frame = Frame(preview)
        control_frame.pack(fill="x", pady=5)
        Button(control_frame, text="Select All", command=self._select_all).pack(side="left", padx=5)
        Button(control_frame, text="Deselect All", command=self._deselect_all).pack(side="left", padx=5)
        Button(control_frame, text="Delete Selected", command=self._delete_selected).pack(side="left", padx=5)

        # Scrollable Canvas setup
        canvas = Canvas(preview)
        canvas.pack(side="left", fill="both", expand=True)
        v_scroll = Scrollbar(preview, orient="vertical", command=canvas.yview)
        v_scroll.pack(side="right", fill="y")
        h_scroll = Scrollbar(preview, orient="horizontal", command=canvas.xview)
        h_scroll.pack(side="bottom", fill="x")
        canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        # This frame will hold all of the pair-frames
        inner = Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")

        # Whenever inner changes size, update scrollable region
        def on_inner_config(evt):
            canvas.configure(scrollregion=canvas.bbox("all"))
        inner.bind("<Configure>", on_inner_config)

        # Build each pair frame (but don’t grid yet)
        pair_frames = []
        for path1, path2 in self.duplicate_pairs:
            pf = Frame(inner, relief="groove", borderwidth=2, padx=5, pady=5)

            # Load thumbnails
            img1 = Image.open(path1); img1.thumbnail((100, 100))
            img2 = Image.open(path2); img2.thumbnail((100, 100))
            photo1 = ImageTk.PhotoImage(img1)
            photo2 = ImageTk.PhotoImage(img2)

            # Place images side-by-side
            lbl1 = Label(pf, image=photo1); lbl1.image = photo1
            lbl2 = Label(pf, image=photo2); lbl2.image = photo2
            lbl1.grid(row=0, column=0, padx=5, pady=5)
            lbl2.grid(row=0, column=1, padx=5, pady=5)

            # Checkboxes directly under each image
            var1 = BooleanVar(value=False)
            var2 = BooleanVar(value=False)
            cb1 = Checkbutton(pf, variable=var1); cb1.grid(row=1, column=0, pady=(0,5))
            cb2 = Checkbutton(pf, variable=var2); cb2.grid(row=1, column=1, pady=(0,5))

            # Track for deletion logic
            self.deletion_vars.extend([var1, var2])
            self.deletion_paths.extend([path1, path2])

            pair_frames.append(pf)

        # Dynamic reflow logic
        def reflow(event=None):
            width = canvas.winfo_width()
            if not pair_frames:
                return
            frame_w = pair_frames[0].winfo_reqwidth() + 20
            # Calculate how many columns fit
            cols = max(1, width // frame_w)
            # Re-grid each frame into the new layout
            for i, pf in enumerate(pair_frames):
                r, c = divmod(i, cols)
                pf.grid(row=r, column=c, padx=10, pady=10, sticky="n")
            # Update scroll region
            canvas.configure(scrollregion=canvas.bbox("all"))

        # Bind reflow on initial draw and on canvas resize
        canvas.bind("<Configure>", reflow)
        preview.update_idletasks()
        reflow()


    def _select_all(self):
        # Loop over all checkbox variables by index, unchecking the first and checking the second image in each pair for a quick removal of duplicates
        for idx, var in enumerate(self.deletion_vars):
            if idx % 2 == 1:
                var.set(True)
            else:
                var.set(False)


    def _deselect_all(self):
        # Like _select_all except only iterating to the odds and unchecking
        for idx, var in enumerate(self.deletion_vars):
            if idx % 2 == 1:
                var.set(False)


    def _delete_selected(self):
        to_trash = [
            path
            for var, path in zip(self.deletion_vars, self.deletion_paths)
            if var.get()
        ]

        if not to_trash:
            messagebox.showinfo("No Selection", "No files were selected to delete.")
            return

        count = len(to_trash)
        proceed = messagebox.askyesno(
            "Confirm Delete",
            f"Permanently delete {count} file"
            + ("s?" if count > 1 else "?")
        )
        if not proceed:
            self.result_list.insert(END, "Deletion cancelled.")
            return

        # Reset any previous undo history
        self.last_deleted.clear()

        # Move each file into .trash
        for orig_path in to_trash:
            try:
                filename = os.path.basename(orig_path)
                trash_path = os.path.join(self.trash_dir, filename)

                # If a file with the same name already exists in .trash, add a numeric suffix to avoid overwriting
                base, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(trash_path):
                    trash_path = os.path.join(
                        self.trash_dir,
                        f"{base}_{counter}{ext}"
                    )
                    counter += 1

                shutil.move(orig_path, trash_path)

                # Record the pair so we can undo
                self.last_deleted.append((orig_path, trash_path))
            except Exception as e:
                self.result_list.insert(
                    END,
                    f"Error moving {orig_path} to trash: {e}"
                )

        # Report what was trashed in the main Listbox
        for orig, _ in self.last_deleted:
            self.result_list.insert(END, f"Moved to trash: {orig}")

        # Enable the "Undo" button now that there is something to undo
        if self.last_deleted:
            self.undo_button.config(state="normal")


    def _undo_delete(self):
        for orig_path, trash_path in self.last_deleted:
            try:
                shutil.move(trash_path, orig_path)
                self.result_list.insert(END, f"Restored: {orig_path}")
            except Exception as e:
                self.result_list.insert(
                    END,
                    f"Error restoring {orig_path}: {e}"
                )

        # Clear the record so it isn't restored twice and disable the button until the next delete
        self.last_deleted.clear()
        self.undo_button.config(state="disabled")


    def _empty_trash(self):
        # List everything currently in the trash folder
        trashed_files = os.listdir(self.trash_dir)

        if not trashed_files:
            messagebox.showinfo("Empty Trash", "Trash is already empty.")
            return

        count = len(trashed_files)
        confirm = messagebox.askyesno(
            "Confirm Empty Trash",
            f"Are you sure you want to permanently delete {count} "
            f"file{'s' if count > 1 else ''} from the trash?"
        )

        if not confirm:
            self.result_list.insert(END, "Empty Trash cancelled.")
            return

        try:
            # Remove the entire trash directory
            shutil.rmtree(self.trash_dir)
            # Recreate an empty trash directory
            os.makedirs(self.trash_dir, exist_ok=True)

            # Clear any undo history and disable “Undo”
            self.last_deleted.clear()
            self.undo_button.config(state="disabled")

            # Report success in the main Listbox
            self.result_list.insert(
                END,
                f"Emptied trash: {count} file{'s' if count > 1 else ''} permanently deleted."
            )
        except Exception as e:
            self.result_list.insert(END, f"Error emptying trash: {e}")


if __name__ == "__main__":
    root = Tk()
    app = DuplicateImageFinder(root)
    root.mainloop()
