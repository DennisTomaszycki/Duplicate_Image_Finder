# Changelog



## [1.2.0] - 2025-07-09

### Added
- Support for scanning **all major image formats** (raster, vector, RAW) via `ALL_IMAGE_EXTS`
- **Cross-platform folder picker** defaults:
  - Windows: “This PC” (all drives)
  - macOS: User’s Home directory (`~/`)
  - Linux/Other: Root folder (`/`)
- **Background scan thread** with live progress updates pushed to the GUI via a `queue.Queue`
- **Thumbnail preview window**:
  - Disabled checkbox on the first (“original”) image in each duplicate group
  - Checkboxes on true duplicates (2nd, 3rd, etc.) for selective deletion
- **Duplicate grouping** (1->N) to handle images with multiple copies without risking deletion of all copies

### Changed
- Switched from pairs `(path1, path2)` model to **group-based** detection (`duplicate_groups`)
- Refactored `show_preview_window` to handle arbitrary group sizes and protect originals

### Fixed
- UI blocking during long scans (now fully non-blocking via threading)
- Possible deletion of the “first” file in a group (now disabled)
- Incorrect initial directory in folder picker on macOS/Linux



## [1.1.0] - 2025-07-06

### Added
- **“Scanning… ##% complete”** label that updates in real time
- **Thumbnail preview window** with:
  - Dynamic multi-column layout that reflows on resize
- **Selective deletion** workflow:
  - App-level “.trash” folder for safe deletes
  - **Undo Last Delete** button to restore trashed files
  - **Empty Trash** button to permanently purge all trashed files

### Changed
- Eliminated auto-deletion of "duplicates" so the user can review and select which images to delete



## [1.0.0] - 2025-06-29

### Added
- Initial Tkinter GUI application for visual duplicate-image detection using perceptual hashing
- **Scrollable Listbox** with horizontal & vertical scrollbars for scan results
- **Optional log file** generation of (`duplicate_log.txt`) when “Create log file of duplicates” is checked
