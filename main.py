import os
import platform
try:
    import win32com.client # type: ignore
except ImportError:
    win32com = None
from tkinter import (
    Tk, Button, Label, filedialog, Listbox, END,
    Checkbutton, BooleanVar, Toplevel, messagebox,
    Canvas, Frame, Scrollbar
)
from PIL import Image, ImageTk
import imagehash
import shutil
import threading
import queue


# Defining and grouping image file extension tuples
RASTER_EXTS = (
    '.png', '.apng', '.jpg', '.jpeg', '.jpe', '.jfif', '.pjpeg', '.pjp',
    '.bmp', '.dib', '.gif', '.tiff', '.tif', '.webp', '.heif', '.heic',
    '.avif', '.jp2', '.j2k', '.jpf', '.jpx', '.jpm', '.mj2', '.jxr', '.hdp',
    '.wdp', '.exr', '.hdr', '.psd', '.psb', '.ico', '.cur', '.xbm', '.xpm',
    '.pcx', '.tga', '.dds', '.ras', '.sgi', '.rgb', '.rgba', '.pic', '.pct',
    '.mng', '.jng', '.bpg', '.flif', '.qoi', '.pam', '.pbm', '.pgm', '.ppm', '.pnm',
)
VECTOR_EXTS = (
    '.svg', '.svgz', '.eps', '.ps', '.ai', '.pdf', '.cdr', '.wmf', '.emf',
    '.dxf', '.cgm', '.vml',
)
RAW_EXTS = (
    '.3fr', '.ari', '.arw', '.srf', '.sr2', '.bay', '.braw', '.cri',
    '.crw', '.cr2', '.cr3', '.cap', '.iiq', '.eip', '.dcs', '.dcr',
    '.drf', '.k25', '.kdc', '.dng', '.erf', '.fff', '.gpr', '.mef',
    '.mdc', '.mos', '.mrw', '.nef', '.nrw', '.orf', '.pef', '.ptx',
    '.pxn', '.r3d', '.raf', '.raw', '.rw2', '.rwl', '.rwz', '.srw',
    '.tco', '.x3f',
)
ALL_IMAGE_EXTS = RASTER_EXTS + VECTOR_EXTS + RAW_EXTS


class DuplicateImageFinder:
    def __init__(self, root):

        self.scan_queue = queue.Queue()

        self.duplicate_pairs = []
        self.deletion_vars = []
        self.deletion_paths = []
        self.last_folder = None
        self.duplicate_groups = []

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

        # Progress tracker
        self.progress_label = Label(root, text="")
        self.progress_label.pack(pady=5)


    def select_folder(self):
        system = platform.system()

        # Always start with the parent of the previous pick
        if self.last_folder:
            start_dir = os.path.dirname(self.last_folder)
        else:
            # If no prior pick is stored, default to the drive directory folder, or root, depending on the OS
            if system == "Windows" and win32com:
                start_dir = None
            elif system == "Darwin":
                start_dir = os.path.expanduser("~")
            else:
                start_dir = os.path.abspath(os.sep)

        # Starting at “This PC” dialog in Windows
        if system == "Windows" and win32com and self.last_folder is None:
            try:
                shell = win32com.client.Dispatch("Shell.Application")
                browse = shell.BrowseForFolder(0, "Select Folder", 0, 17)
                folder_path = browse.Self.Path if browse else None
            except Exception:
                folder_path = filedialog.askdirectory()
        else:
            # Non-Windows or after first pick on Windows
            folder_path = filedialog.askdirectory(initialdir=start_dir)

        if folder_path:
            self.last_folder = folder_path
            
            self.select_button.config(state='disabled')
            self.preview_button.config(state='disabled')
            self.result_list.delete(0, END)
            self.progress_label.config(text="Scanning... 0% complete")

            self.deletion_vars.clear()
            self.deletion_paths.clear()

            # Start the worker thread
            thread = threading.Thread(
                target=self._scan_thread,
                args=(folder_path,),
                daemon=True
            )
            thread.start()

            # Begin polling the queue every 100 ms
            self.root.after(100, self._process_scan_queue)


    def _scan_thread(self, folder_path):
        # Gather all image paths
        image_paths = []
        for dirpath, _, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(ALL_IMAGE_EXTS):
                    image_paths.append(os.path.join(dirpath, file))
        total = len(image_paths)

        # If nothing to do, send done immediately
        if total == 0:
            self.scan_queue.put(('done', []))
            return

        hashes = {}
        for idx, path in enumerate(image_paths, start=1):
            filename = os.path.basename(path)
            try:
                img = Image.open(path)
                h = imagehash.phash(img)
                hashes.setdefault(h, []).append(path)
            except Exception as e:
                self.scan_queue.put(('error', filename, str(e)))
            # Progress update
            pct = int(idx/total*100)
            self.scan_queue.put(('progress', pct))

        # Retreive groups with more than one image
        self.duplicate_groups = [grp for grp in hashes.values() if len(grp) > 1]

        # Scanning done, send duplicates list
        self.scan_queue.put(('done', self.duplicate_groups))


    def _process_scan_queue(self):
        try:
            while True:
                msg = self.scan_queue.get_nowait()
                tag = msg[0]

                if tag == 'progress':
                    _, pct = msg
                    self.progress_label.config(text=f"Scanning... {pct}% complete")

                elif tag == 'error':
                    _, filename, error = msg
                    self.result_list.insert(END, f"Error: {filename} ({error})")

                elif tag == 'done':
                    _, duplicates = msg
                    # Hand off to completion handler
                    self._on_scan_complete(duplicates)
                    return  # stop processing after 'done'
        except queue.Empty:
            # No more messages right now
            pass

        # If not 'done' yet, poll again
        self.root.after(100, self._process_scan_queue)


    def _on_scan_complete(self, groups):
        self.progress_label.config(text="Scan complete.")
        self.select_button.config(state='normal')

        # Optional log
        if groups and self.log_var.get():
            log_file = os.path.join(os.getcwd(), 'duplicate_log.txt')
            try:
                with open(log_file, 'w') as f:
                    f.write('Duplicate groups:\n')
                    for grp in groups:
                        f.write(", ".join(grp) + "\n")
                self.result_list.insert(END, f"Log file created at {log_file}")
            except Exception as e:
                self.result_list.insert(END, f"Error writing log file: {e}")

        # Show results & enable preview if needed
        if groups:
            for grp in groups:
                # Show first two paths in the preview list
                self.result_list.insert(
                    END,
                    "Duplicate Group:\n  " + "\n  ".join(grp) + "\n"
                )
            self.preview_button.config(state='normal')
        else:
            self.result_list.insert(END, "No duplicates found.")


    def show_preview_window(self):
        if not self.duplicate_groups:
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

        # Reset deletion tracking
        self.deletion_vars.clear()
        self.deletion_paths.clear()

        # Build each pair frame (but don’t grid yet)
        pair_frames = []
        for group in self.duplicate_groups:
            pf = Frame(inner, relief="groove", borderwidth=2, padx=5, pady=5)

            for idx, path in enumerate(group):
                # Load and thumbnail the image
                img = Image.open(path)
                img.thumbnail((100, 100))
                photo = ImageTk.PhotoImage(img)

                # Place the image
                lbl = Label(pf, image=photo)
                lbl.image = photo  # keep a reference!
                lbl.grid(row=0, column=idx, padx=5, pady=5)

                # First image is protected: disabled checkbox
                if idx == 0:
                    cb = Checkbutton(pf, state='disabled')
                    cb.grid(row=1, column=idx, pady=(0, 5))
                else:
                    # True duplicates get a real checkbox
                    var = BooleanVar(value=False)
                    cb = Checkbutton(pf, variable=var)
                    cb.grid(row=1, column=idx, pady=(0, 5))

                    # Track for deletion
                    self.deletion_vars.append(var)
                    self.deletion_paths.append(path)

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
        for var in self.deletion_vars:
            var.set(True)


    def _deselect_all(self):
        for var in self.deletion_vars:
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
