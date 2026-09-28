"""Tkinter desktop interface for SortMate."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from .core import MovePlan, SortMateError, apply_plan, create_plan, undo_last


def format_size(size: int) -> str:
    value = float(size)
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if value < 1024 or unit == "ТБ":
            return f"{value:.0f} {unit}" if unit == "Б" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} ТБ"


class SortMateApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("SortMate — файловый помощник")
        self.root.geometry("940x640")
        self.root.minsize(760, 520)
        self.root.configure(bg="#f4f6f8")

        self.folder = tk.StringVar()
        self.mode = tk.StringVar(value="category")
        self.status = tk.StringVar(value="Выберите папку и посмотрите план сортировки.")
        self.plan: MovePlan | None = None

        self._configure_style()
        self._build_ui()

    def _configure_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#f4f6f8")
        style.configure("Panel.TFrame", background="#ffffff")
        style.configure("TLabel", background="#f4f6f8", foreground="#24313d", font=("Segoe UI", 10))
        style.configure("Title.TLabel", background="#f4f6f8", foreground="#17212b", font=("Segoe UI Semibold", 22))
        style.configure("Hint.TLabel", background="#f4f6f8", foreground="#657381", font=("Segoe UI", 9))
        style.configure("Status.TLabel", background="#e9eef3", foreground="#3e4c59", padding=(12, 8))
        style.configure("Treeview", rowheight=28, font=("Segoe UI", 9), background="#ffffff", fieldbackground="#ffffff")
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 9), background="#e9eef3", foreground="#24313d")
        style.map("Treeview", background=[("selected", "#dcecff")], foreground=[("selected", "#17212b")])
        style.configure("Accent.TButton", font=("Segoe UI Semibold", 10), padding=(12, 8))
        style.configure("TButton", font=("Segoe UI", 9), padding=(10, 7))
        style.configure("TRadiobutton", background="#f4f6f8", font=("Segoe UI", 9))

    def _build_ui(self) -> None:
        page = ttk.Frame(self.root, padding=(24, 20))
        page.pack(fill="both", expand=True)

        header = ttk.Frame(page)
        header.pack(fill="x")
        ttk.Label(header, text="SortMate", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="Сначала просмотр. Перемещение — только после вашего подтверждения.", style="Hint.TLabel").pack(side="left", padx=(16, 0), pady=(10, 0))

        picker = ttk.Frame(page, style="Panel.TFrame", padding=14)
        picker.pack(fill="x", pady=(18, 12))
        ttk.Label(picker, text="Папка для сортировки", background="#ffffff", font=("Segoe UI Semibold", 10)).pack(anchor="w")
        line = ttk.Frame(picker, style="Panel.TFrame")
        line.pack(fill="x", pady=(8, 10))
        self.folder_entry = ttk.Entry(line, textvariable=self.folder)
        self.folder_entry.pack(side="left", fill="x", expand=True, ipady=5)
        ttk.Button(line, text="Выбрать папку…", command=self.choose_folder).pack(side="left", padx=(8, 0))

        controls = ttk.Frame(picker, style="Panel.TFrame")
        controls.pack(fill="x")
        ttk.Label(controls, text="Разложить по:", background="#ffffff").pack(side="left", padx=(0, 8))
        ttk.Radiobutton(controls, text="Типу файлов", variable=self.mode, value="category", command=self.refresh_plan).pack(side="left")
        ttk.Radiobutton(controls, text="Месяцу изменения", variable=self.mode, value="month", command=self.refresh_plan).pack(side="left", padx=(10, 14))
        ttk.Button(controls, text="Предпросмотр", style="Accent.TButton", command=self.refresh_plan).pack(side="left")

        summary = ttk.Frame(page)
        summary.pack(fill="x", pady=(5, 7))
        self.summary_label = ttk.Label(summary, text="Предпросмотр ещё не построен", font=("Segoe UI Semibold", 10))
        self.summary_label.pack(side="left")
        ttk.Label(summary, text="Сортируются только файлы в выбранной папке; вложенные папки не затрагиваются.", style="Hint.TLabel").pack(side="right")

        table_frame = ttk.Frame(page)
        table_frame.pack(fill="both", expand=True)
        columns = ("name", "size", "destination")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
        self.table.heading("name", text="Файл")
        self.table.heading("size", text="Размер")
        self.table.heading("destination", text="Папка назначения")
        self.table.column("name", width=430, minwidth=180, anchor="w")
        self.table.column("size", width=100, minwidth=85, anchor="e")
        self.table.column("destination", width=250, minwidth=140, anchor="w")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        footer = ttk.Frame(page)
        footer.pack(fill="x", pady=(12, 0))
        ttk.Label(footer, textvariable=self.status, style="Status.TLabel").pack(side="left", fill="x", expand=True)
        self.undo_button = ttk.Button(footer, text="Отменить последнюю сортировку", command=self.undo)
        self.undo_button.pack(side="right", padx=(8, 0))
        self.apply_button = ttk.Button(footer, text="Сортировать", style="Accent.TButton", command=self.apply)
        self.apply_button.pack(side="right")
        self.apply_button.state(["disabled"])

    def choose_folder(self) -> None:
        initial = self.folder.get() if Path(self.folder.get()).is_dir() else str(Path.home())
        selected = filedialog.askdirectory(title="Выберите папку", initialdir=initial, mustexist=True)
        if selected:
            self.folder.set(selected)
            self.refresh_plan()

    def refresh_plan(self) -> None:
        folder = self.folder.get().strip()
        if not folder:
            self.status.set("Сначала выберите папку.")
            return
        try:
            self.plan = create_plan(folder, self.mode.get())
        except SortMateError as error:
            self.plan = None
            self._clear_table()
            self.summary_label.configure(text="Предпросмотр недоступен")
            self.apply_button.state(["disabled"])
            self.status.set(str(error))
            return

        self._clear_table()
        display_items = self.plan.items[:2000]
        for item in display_items:
            relative_destination = item.target.relative_to(self.plan.root)
            self.table.insert("", "end", values=(item.source.name, format_size(item.size), str(relative_destination)))

        count = len(self.plan.items)
        self.summary_label.configure(text=f"К сортировке: {count} файлов · {format_size(self.plan.total_bytes)}")
        if count:
            self.apply_button.state(["!disabled"])
            hidden_count = count - len(display_items)
            suffix = f" В таблице показаны первые {len(display_items)}; всего будет обработано {count}." if hidden_count > 0 else ""
            self.status.set("Проверьте список. Ничего не перемещено." + suffix)
        else:
            self.apply_button.state(["disabled"])
            self.status.set("В выбранной папке нет файлов для сортировки.")

    def _clear_table(self) -> None:
        for row in self.table.get_children():
            self.table.delete(row)

    def apply(self) -> None:
        if not self.plan or not self.plan.items:
            return
        mode_text = "по типам файлов" if self.plan.mode == "category" else "по месяцам изменения"
        confirmed = messagebox.askyesno(
            "Подтвердите сортировку",
            f"Переместить {len(self.plan.items)} файлов {mode_text}?\n\n"
            f"Папка: {self.plan.root}\n\n"
            "Если в папке назначения уже есть файл с таким именем, SortMate добавит номер и не перезапишет его.\n"
            "Последнюю сортировку можно будет отменить.",
            icon="question",
            parent=self.root,
        )
        if not confirmed:
            return
        try:
            transaction = apply_plan(self.plan)
        except SortMateError as error:
            messagebox.showerror("Не удалось завершить сортировку", str(error), parent=self.root)
            self.refresh_plan()
            return

        count = len(transaction["moves"])
        self.status.set(f"Готово: перемещено файлов — {count}. Последнюю сортировку можно отменить.")
        self.refresh_plan()

    def undo(self) -> None:
        if not messagebox.askyesno(
            "Отменить сортировку",
            "Вернуть файлы из последней сортировки в исходные папки?\n\n"
            "Если исходное имя уже занято, отмена остановится без перезаписи.",
            icon="question",
            parent=self.root,
        ):
            return
        try:
            count = undo_last()
        except SortMateError as error:
            messagebox.showerror("Не удалось отменить", str(error), parent=self.root)
            return
        self.status.set(f"Отменено: восстановлено файлов — {count}.")
        self.refresh_plan()


def main() -> None:
    root = tk.Tk()
    SortMateApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
