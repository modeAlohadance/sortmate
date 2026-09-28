"""Safe, previewable file organization and reversible move operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import uuid


CATEGORIES: dict[str, set[str]] = {
    "Images": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".svg", ".ico"},
    "Documents": {".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".pages"},
    "Spreadsheets": {".xls", ".xlsx", ".ods", ".csv", ".tsv"},
    "Presentations": {".ppt", ".pptx", ".odp", ".key"},
    "Audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"},
    "Video": {".mp4", ".mov", ".mkv", ".avi", ".webm", ".wmv", ".m4v"},
    "Archives": {".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz"},
    "Installers": {".exe", ".msi", ".msix", ".appx", ".deb", ".rpm", ".dmg", ".pkg"},
    "Code": {".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".yml", ".yaml", ".toml", ".sql", ".sh", ".ps1", ".java", ".cs", ".go", ".rs", ".cpp", ".h"},
}


@dataclass(frozen=True, slots=True)
class PlanItem:
    source: Path
    target: Path
    group: str
    size: int


@dataclass(frozen=True, slots=True)
class MovePlan:
    root: Path
    mode: str
    items: tuple[PlanItem, ...]
    total_bytes: int


class SortMateError(Exception):
    """An expected, user-facing operation error."""


def _category(path: Path) -> str:
    extension = path.suffix.lower()
    for name, extensions in CATEGORIES.items():
        if extension in extensions:
            return name
    return "Other"


def _available_target(directory: Path, filename: str, reserved: set[Path]) -> Path:
    candidate = directory / filename
    if candidate not in reserved and not candidate.exists():
        reserved.add(candidate)
        return candidate

    original = Path(filename)
    number = 1
    while True:
        suffix = f" ({number})"
        name = f"{original.stem}{suffix}{original.suffix}"
        candidate = directory / name
        if candidate not in reserved and not candidate.exists():
            reserved.add(candidate)
            return candidate
        number += 1


def create_plan(folder: str | Path, mode: str = "category") -> MovePlan:
    """Plan moves for regular files directly inside *folder*; never recurse."""

    root = Path(folder).expanduser()
    if not root.exists() or not root.is_dir():
        raise SortMateError("Выберите существующую папку.")
    if mode not in {"category", "month"}:
        raise SortMateError("Неизвестный способ сортировки.")

    root = root.resolve()
    items: list[PlanItem] = []
    reserved: set[Path] = set()
    try:
        entries = sorted(root.iterdir(), key=lambda entry: entry.name.casefold())
        for source in entries:
            if source.is_symlink() or not source.is_file():
                continue
            stat = source.stat()
            group = _category(source) if mode == "category" else datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m")
            destination_folder = root / group
            if destination_folder.exists() and not destination_folder.is_dir():
                raise SortMateError(f"Нельзя создать папку «{group}»: файл с таким именем уже существует.")
            target = _available_target(destination_folder, source.name, reserved)
            items.append(PlanItem(source, target, group, stat.st_size))
    except OSError as error:
        raise SortMateError(f"Не удалось прочитать папку: {error}") from error

    return MovePlan(root, mode, tuple(items), sum(item.size for item in items))


def _history_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    return Path(base) / "SortMate" / "history.json"


def _load_history(path: Path | None = None) -> list[dict[str, object]]:
    history_path = path or _history_path()
    try:
        data = json.loads(history_path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except FileNotFoundError:
        return []
    except (OSError, json.JSONDecodeError):
        raise SortMateError("Не удалось прочитать историю. Файлы не изменены.")


def _save_history(history: list[dict[str, object]], path: Path | None = None) -> None:
    history_path = path or _history_path()
    try:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = history_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(history[-20:], ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(history_path)
    except OSError as error:
        raise SortMateError(f"Не удалось сохранить историю операций: {error}") from error


def apply_plan(plan: MovePlan, history_path: Path | None = None) -> dict[str, object]:
    """Move every still-valid source. Roll back prior moves if the batch fails."""

    moved: list[dict[str, str]] = []
    created_dirs: set[Path] = set()
    try:
        for item in plan.items:
            source = item.source
            if source.parent.resolve() != plan.root or source.is_symlink() or not source.is_file():
                raise SortMateError(f"Файл изменился после просмотра: {source.name}")
            destination_dir = plan.root / item.group
            if destination_dir.exists() and not destination_dir.is_dir():
                raise SortMateError(f"Папка назначения занята файлом: {item.group}")
            if not destination_dir.exists():
                destination_dir.mkdir()
                created_dirs.add(destination_dir)

            destination = item.target
            if destination.exists():
                destination = _available_target(destination_dir, source.name, set())
            source.rename(destination)
            moved.append({"source": str(source), "destination": str(destination)})
    except Exception as error:
        rollback_errors: list[str] = []
        for record in reversed(moved):
            source, destination = Path(record["source"]), Path(record["destination"])
            try:
                if destination.exists() and not source.exists():
                    destination.rename(source)
            except OSError:
                rollback_errors.append(source.name)
        for directory in sorted(created_dirs, key=lambda value: len(value.parts), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass
        if isinstance(error, SortMateError):
            detail = str(error)
        else:
            detail = str(error)
        if rollback_errors:
            detail += " Не удалось вернуть файлы: " + ", ".join(rollback_errors)
        raise SortMateError(f"Сортировка остановлена. {detail}") from error

    transaction: dict[str, object] = {
        "id": uuid.uuid4().hex,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "root": str(plan.root),
        "mode": plan.mode,
        "moves": moved,
    }
    try:
        history = _load_history(history_path)
        history.append(transaction)
        _save_history(history, history_path)
    except SortMateError as error:
        rollback_errors = []
        for record in reversed(moved):
            source, destination = Path(record["source"]), Path(record["destination"])
            try:
                if destination.exists() and not source.exists():
                    destination.rename(source)
            except OSError:
                rollback_errors.append(source.name)
        if rollback_errors:
            raise SortMateError(f"{error} Не удалось вернуть файлы: {', '.join(rollback_errors)}") from error
        raise
    return transaction


def undo_last(history_path: Path | None = None) -> int:
    """Undo the latest transaction after verifying every path first."""

    history = _load_history(history_path)
    if not history:
        raise SortMateError("Нет сортировки, которую можно отменить.")
    transaction = history[-1]
    records = transaction.get("moves", [])
    if not isinstance(records, list) or not records:
        raise SortMateError("Последняя операция не содержит записей для отмены.")

    pairs: list[tuple[Path, Path]] = []
    for record in records:
        try:
            original = Path(str(record["source"]))
            organized = Path(str(record["destination"]))
        except (KeyError, TypeError) as error:
            raise SortMateError("История повреждена; файлы не изменены.") from error
        if original.exists():
            raise SortMateError(f"Нельзя отменить без перезаписи: файл уже существует — {original.name}")
        if not organized.exists() or not organized.is_file():
            raise SortMateError(f"Не найден перемещённый файл: {organized.name}. Файлы не изменены.")
        pairs.append((organized, original))

    restored: list[tuple[Path, Path]] = []
    try:
        for organized, original in reversed(pairs):
            original.parent.mkdir(parents=True, exist_ok=True)
            organized.rename(original)
            restored.append((organized, original))
    except OSError as error:
        for organized, original in reversed(restored):
            try:
                if original.exists() and not organized.exists():
                    original.rename(organized)
            except OSError:
                pass
        raise SortMateError(f"Отмена остановлена: {error}") from error

    history.pop()
    _save_history(history, history_path)
    return len(restored)
