# SortMate

SortMate is a small Windows desktop helper for tidying a folder without guessing what it will do. Choose a folder, preview where each file would go, then confirm before anything moves. The app can restore the most recent sort and never replaces an existing file.

## What it does

- Sorts files directly inside one selected folder by file type or modification month.
- Shows a preview with each file's destination and size before moving anything.
- Leaves subfolders and their contents untouched.
- Adds a numbered suffix when a destination filename already exists.
- Stores a local move history so the latest batch can be undone.
- Uses Python's standard library; it does not upload filenames or file contents.

## Run on Windows

Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/windows/) and enable the Tcl/Tk option in the installer. Then download this repository and double-click `run.bat`, or launch it from PowerShell:

```powershell
py -3 main.py
```

No administrator rights or extra Python packages are needed.

## How sorting works

**By file type** groups common formats into `Images`, `Documents`, `Spreadsheets`, `Presentations`, `Audio`, `Video`, `Archives`, `Installers`, `Code`, and `Other`.

**By modification month** makes folders such as `2026-09` using each file's last-modified date.

The scan is deliberately limited to the top level of the folder you choose. SortMate never reads file contents. Before moving, it checks that the previewed files still exist. If a move fails, it attempts to return files already moved in that batch.

## Undo and history

The most recent operation can be undone from the app. The move journal is stored at `%LOCALAPPDATA%\SortMate\history.json` on Windows. It records the source and destination paths needed to restore files. The app retains up to 20 recent operations.

Undo checks every original path before restoring anything. If an original filename is occupied, it stops instead of overwriting that file. If you manually rename or delete a moved file after sorting, the app explains that it cannot restore the missing item.

## Limits

- The app organizes files; it does not delete files or find duplicate contents.
- The undo journal is local to this Windows account and device.
- Use undo before doing additional manual moves if you want to restore a batch reliably.

## Development

The UI uses `tkinter`; file planning and reversible move logic live in `src/sortmate/core.py`. The app requires no network access.

## License

MIT. See [LICENSE](LICENSE).
