from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QSpinBox,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.experimental.pyqt_schema_project.controller import PyQtSchemaProjectController
from src.experimental.pyqt_schema_project.json_editor import JsonEditorDialog
from src.experimental.pyqt_schema_project.models import DictTableModel
from src.gui_schema_shared import DTYPES
from src.gui_v2.generator_forms import visible_fields_for


class ExperimentalSchemaProjectWindow(QMainWindow):
    """Optional isolated PyQt schema-project editor experiment."""

    def __init__(self, *, initial_schema_path: str | None = None) -> None:
        super().__init__()
        self.controller = PyQtSchemaProjectController()
        self.setWindowTitle("Schema Project PyQt Experiment")
        self.resize(1500, 920)

        self._form_inputs: dict[str, QLineEdit] = {}
        self._column_columns = ["name", "dtype", "nullable", "primary_key", "unique", "generator", "depends_on"]
        self._fk_columns = ["index", "child_table", "child_column", "parent_table", "parent_column", "min_children", "max_children"]

        self._build_ui()
        self._bind_shortcuts()

        if initial_schema_path:
            try:
                self.controller.load_project(initial_schema_path)
                self._status(f"Loaded schema from {initial_schema_path}.")
            except Exception as exc:  # noqa: BLE001
                self._show_error(exc)

        self._refresh_all()

    def _build_ui(self) -> None:
        self._build_toolbar()

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.setCentralWidget(splitter)

        left = QWidget(splitter)
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Tables"))

        self.table_list = QListWidget(left)
        self.table_list.currentItemChanged.connect(self._on_table_selected)
        left_layout.addWidget(self.table_list, 1)

        left_btns = QHBoxLayout()
        self.add_table_btn = QPushButton("Add table", left)
        self.add_table_btn.clicked.connect(self._on_add_table)
        self.remove_table_btn = QPushButton("Remove table", left)
        self.remove_table_btn.clicked.connect(self._on_remove_table)
        left_btns.addWidget(self.add_table_btn)
        left_btns.addWidget(self.remove_table_btn)
        left_layout.addLayout(left_btns)

        right = QWidget(splitter)
        right_layout = QVBoxLayout(right)

        self.tabs = QTabWidget(right)
        right_layout.addWidget(self.tabs, 1)

        self.project_tab = QWidget(self.tabs)
        self.columns_tab = QWidget(self.tabs)
        self.relationships_tab = QWidget(self.tabs)
        self.generate_tab = QWidget(self.tabs)

        self.tabs.addTab(self.project_tab, "Project")
        self.tabs.addTab(self.columns_tab, "Columns")
        self.tabs.addTab(self.relationships_tab, "Relationships")
        self.tabs.addTab(self.generate_tab, "Generate")

        self._build_project_tab()
        self._build_columns_tab()
        self._build_relationships_tab()
        self._build_generate_tab()

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

    def _build_toolbar(self) -> None:
        bar = self.addToolBar("Main")
        bar.setMovable(False)

        new_action = QAction("New", self)
        new_action.triggered.connect(self._on_new_project)
        bar.addAction(new_action)

        load_action = QAction("Load", self)
        load_action.triggered.connect(self._on_load_project)
        bar.addAction(load_action)

        save_action = QAction("Save", self)
        save_action.triggered.connect(self._on_save_project)
        bar.addAction(save_action)

        validate_action = QAction("Validate", self)
        validate_action.triggered.connect(self._on_validate)
        bar.addAction(validate_action)

        preview_action = QAction("Generate Preview", self)
        preview_action.triggered.connect(self._on_generate_preview)
        bar.addAction(preview_action)

        export_csv_action = QAction("Export CSV", self)
        export_csv_action.triggered.connect(self._on_export_csv)
        bar.addAction(export_csv_action)

        export_sqlite_action = QAction("Export SQLite", self)
        export_sqlite_action.triggered.connect(self._on_export_sqlite)
        bar.addAction(export_sqlite_action)

        undo_action = QAction("Undo", self)
        undo_action.triggered.connect(self._on_undo)
        bar.addAction(undo_action)

        redo_action = QAction("Redo", self)
        redo_action.triggered.connect(self._on_redo)
        bar.addAction(redo_action)

    def _build_project_tab(self) -> None:
        layout = QVBoxLayout(self.project_tab)
        form = QFormLayout()

        self.project_name_edit = QLineEdit(self.project_tab)
        self.seed_spin = QSpinBox(self.project_tab)
        self.seed_spin.setRange(0, 2_147_483_647)
        self.mode_combo = QComboBox(self.project_tab)
        self.mode_combo.addItems(["simple", "medium", "complex"])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)

        form.addRow("Project name", self.project_name_edit)
        form.addRow("Seed", self.seed_spin)
        form.addRow("Design mode", self.mode_combo)
        layout.addLayout(form)

        self.timeline_json = QPlainTextEdit(self.project_tab)
        self.quality_json = QPlainTextEdit(self.project_tab)
        self.fits_json = QPlainTextEdit(self.project_tab)
        self.locale_json = QPlainTextEdit(self.project_tab)

        layout.addWidget(self._json_group("Timeline constraints JSON", self.timeline_json))
        layout.addWidget(self._json_group("Data quality profiles JSON", self.quality_json))
        layout.addWidget(self._json_group("Sample profile fits JSON", self.fits_json))
        layout.addWidget(self._json_group("Locale identity bundles JSON", self.locale_json))

        apply_btn = QPushButton("Apply project settings", self.project_tab)
        apply_btn.clicked.connect(self._apply_project_settings)
        layout.addWidget(apply_btn)

    def _json_group(self, title: str, editor: QPlainTextEdit) -> QWidget:
        group = QGroupBox(title, self.project_tab)
        inner = QVBoxLayout(group)
        inner.addWidget(editor)
        row = QHBoxLayout()
        open_btn = QPushButton("Open JSON editor", group)
        open_btn.clicked.connect(lambda: self._open_json_dialog(editor, title))
        row.addWidget(open_btn)
        row.addStretch(1)
        inner.addLayout(row)
        return group

    def _build_columns_tab(self) -> None:
        layout = QVBoxLayout(self.columns_tab)
        form = QGridLayout()

        self.col_name = QLineEdit(self.columns_tab)
        self.col_dtype = QComboBox(self.columns_tab)
        self.col_dtype.addItems(DTYPES)
        self.col_dtype.currentTextChanged.connect(self._on_dtype_changed)
        self.col_pk = QCheckBox("Primary key", self.columns_tab)
        self.col_nullable = QCheckBox("Nullable", self.columns_tab)
        self.col_nullable.setChecked(True)
        self.col_unique = QCheckBox("Unique", self.columns_tab)
        self.col_generator = QComboBox(self.columns_tab)
        self.col_generator.currentTextChanged.connect(self._on_generator_changed)
        self.col_depends_on = QLineEdit(self.columns_tab)
        self.col_min = QLineEdit(self.columns_tab)
        self.col_max = QLineEdit(self.columns_tab)
        self.col_choices = QLineEdit(self.columns_tab)
        self.col_pattern = QLineEdit(self.columns_tab)
        self.col_params = QPlainTextEdit(self.columns_tab)

        form.addWidget(QLabel("Column name"), 0, 0)
        form.addWidget(self.col_name, 0, 1)
        form.addWidget(QLabel("Dtype"), 0, 2)
        form.addWidget(self.col_dtype, 0, 3)
        form.addWidget(self.col_pk, 1, 0)
        form.addWidget(self.col_nullable, 1, 1)
        form.addWidget(self.col_unique, 1, 2)
        form.addWidget(QLabel("Generator"), 2, 0)
        form.addWidget(self.col_generator, 2, 1, 1, 3)
        form.addWidget(QLabel("Depends on (csv)"), 3, 0)
        form.addWidget(self.col_depends_on, 3, 1, 1, 3)
        form.addWidget(QLabel("Min"), 4, 0)
        form.addWidget(self.col_min, 4, 1)
        form.addWidget(QLabel("Max"), 4, 2)
        form.addWidget(self.col_max, 4, 3)
        form.addWidget(QLabel("Choices (csv)"), 5, 0)
        form.addWidget(self.col_choices, 5, 1, 1, 3)
        form.addWidget(QLabel("Pattern"), 6, 0)
        form.addWidget(self.col_pattern, 6, 1, 1, 3)
        form.addWidget(QLabel("Params JSON"), 7, 0)
        form.addWidget(self.col_params, 7, 1, 1, 3)
        layout.addLayout(form)

        self.structured_form_group = QGroupBox("Structured Generator Form", self.columns_tab)
        self.structured_form_layout = QFormLayout(self.structured_form_group)
        layout.addWidget(self.structured_form_group)

        row = QHBoxLayout()
        self.reload_form_btn = QPushButton("Reload form from params", self.columns_tab)
        self.reload_form_btn.clicked.connect(self._reload_form_from_params)
        self.sync_form_btn = QPushButton("Sync form -> params", self.columns_tab)
        self.sync_form_btn.clicked.connect(self._sync_form_to_params)
        self.add_col_btn = QPushButton("Add column", self.columns_tab)
        self.add_col_btn.clicked.connect(self._on_add_column)
        self.update_col_btn = QPushButton("Update selected column", self.columns_tab)
        self.update_col_btn.clicked.connect(self._on_update_column)
        self.remove_col_btn = QPushButton("Remove selected column", self.columns_tab)
        self.remove_col_btn.clicked.connect(self._on_remove_column)
        row.addWidget(self.reload_form_btn)
        row.addWidget(self.sync_form_btn)
        row.addWidget(self.add_col_btn)
        row.addWidget(self.update_col_btn)
        row.addWidget(self.remove_col_btn)
        layout.addLayout(row)

        self.columns_model = DictTableModel()
        self.columns_table = QTableView(self.columns_tab)
        self.columns_table.setModel(self.columns_model)
        self.columns_table.clicked.connect(self._on_column_row_clicked)
        layout.addWidget(self.columns_table, 1)

    def _build_relationships_tab(self) -> None:
        layout = QVBoxLayout(self.relationships_tab)
        form = QGridLayout()
        self.fk_child_table = QComboBox(self.relationships_tab)
        self.fk_child_column = QComboBox(self.relationships_tab)
        self.fk_parent_table = QComboBox(self.relationships_tab)
        self.fk_parent_column = QComboBox(self.relationships_tab)
        self.fk_min_children = QSpinBox(self.relationships_tab)
        self.fk_max_children = QSpinBox(self.relationships_tab)
        for spin in (self.fk_min_children, self.fk_max_children):
            spin.setRange(0, 1_000_000)
        self.fk_min_children.setValue(1)
        self.fk_max_children.setValue(3)
        self.fk_parent_selection = QPlainTextEdit(self.relationships_tab)
        self.fk_child_distribution = QPlainTextEdit(self.relationships_tab)

        self.fk_child_table.currentTextChanged.connect(self._refresh_fk_column_combos)
        self.fk_parent_table.currentTextChanged.connect(self._refresh_fk_column_combos)

        form.addWidget(QLabel("Child table"), 0, 0)
        form.addWidget(self.fk_child_table, 0, 1)
        form.addWidget(QLabel("Child column"), 0, 2)
        form.addWidget(self.fk_child_column, 0, 3)
        form.addWidget(QLabel("Parent table"), 1, 0)
        form.addWidget(self.fk_parent_table, 1, 1)
        form.addWidget(QLabel("Parent column"), 1, 2)
        form.addWidget(self.fk_parent_column, 1, 3)
        form.addWidget(QLabel("Min children"), 2, 0)
        form.addWidget(self.fk_min_children, 2, 1)
        form.addWidget(QLabel("Max children"), 2, 2)
        form.addWidget(self.fk_max_children, 2, 3)
        form.addWidget(QLabel("Parent selection JSON"), 3, 0)
        form.addWidget(self.fk_parent_selection, 3, 1, 1, 3)
        form.addWidget(QLabel("Child distribution JSON"), 4, 0)
        form.addWidget(self.fk_child_distribution, 4, 1, 1, 3)
        layout.addLayout(form)

        btns = QHBoxLayout()
        add_btn = QPushButton("Add relationship", self.relationships_tab)
        add_btn.clicked.connect(self._on_add_fk)
        remove_btn = QPushButton("Remove selected relationship", self.relationships_tab)
        remove_btn.clicked.connect(self._on_remove_fk)
        btns.addWidget(add_btn)
        btns.addWidget(remove_btn)
        layout.addLayout(btns)

        self.fk_model = DictTableModel()
        self.fk_table = QTableView(self.relationships_tab)
        self.fk_table.setModel(self.fk_model)
        self.fk_table.clicked.connect(self._on_fk_row_clicked)
        layout.addWidget(self.fk_table, 1)

    def _build_generate_tab(self) -> None:
        layout = QVBoxLayout(self.generate_tab)
        btns = QHBoxLayout()
        validate_btn = QPushButton("Validate", self.generate_tab)
        validate_btn.clicked.connect(self._on_validate)
        generate_btn = QPushButton("Generate preview", self.generate_tab)
        generate_btn.clicked.connect(self._on_generate_preview)
        export_csv_btn = QPushButton("Export CSV", self.generate_tab)
        export_csv_btn.clicked.connect(self._on_export_csv)
        export_sqlite_btn = QPushButton("Export SQLite", self.generate_tab)
        export_sqlite_btn.clicked.connect(self._on_export_sqlite)
        btns.addWidget(validate_btn)
        btns.addWidget(generate_btn)
        btns.addWidget(export_csv_btn)
        btns.addWidget(export_sqlite_btn)
        layout.addLayout(btns)

        layout.addWidget(QLabel("Validation issues"))
        self.validation_list = QListWidget(self.generate_tab)
        layout.addWidget(self.validation_list)

        table_row = QHBoxLayout()
        table_row.addWidget(QLabel("Preview table"))
        self.preview_table_combo = QComboBox(self.generate_tab)
        self.preview_table_combo.currentTextChanged.connect(self._refresh_preview_grid)
        table_row.addWidget(self.preview_table_combo)
        table_row.addStretch(1)
        layout.addLayout(table_row)

        self.preview_model = DictTableModel()
        self.preview_table = QTableView(self.generate_tab)
        self.preview_table.setModel(self.preview_model)
        layout.addWidget(self.preview_table, 1)

    def _bind_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self._on_undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, activated=self._on_redo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, activated=self._on_redo)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._on_save_project)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self._on_load_project)

    def _status(self, message: str) -> None:
        self.statusBar().showMessage(message, 9000)

    def _show_error(self, error: Exception | str) -> None:
        message = str(error)
        QMessageBox.critical(self, "PyQt schema experiment error", message)
        self._status(message)

    def _selected_table_name(self) -> str | None:
        item = self.table_list.currentItem()
        return None if item is None else item.text()

    def _on_new_project(self) -> None:
        self.controller = PyQtSchemaProjectController()
        self._refresh_all()
        self._status("Created a new experimental schema project.")

    def _on_load_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open schema project JSON", "", "JSON files (*.json)")
        if not path:
            return
        try:
            self.controller.load_project(path)
            self._refresh_all()
            self._status(f"Loaded {path}.")
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _on_save_project(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save schema project JSON", "", "JSON files (*.json)")
        if not path:
            return
        try:
            self.controller.save_project(path)
            self._status(f"Saved {path}.")
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _open_json_dialog(self, editor: QPlainTextEdit, title: str) -> None:
        accepted, text = JsonEditorDialog.edit_json(self, title=title, initial_text=editor.toPlainText())
        if accepted:
            editor.setPlainText(text)

    def _apply_project_settings(self) -> None:
        try:
            self.controller.set_project_metadata(name=self.project_name_edit.text(), seed=self.seed_spin.value())
            self.controller.set_project_level_json(
                timeline_constraints_json=self.timeline_json.toPlainText(),
                data_quality_profiles_json=self.quality_json.toPlainText(),
                sample_profile_fits_json=self.fits_json.toPlainText(),
                locale_identity_bundles_json=self.locale_json.toPlainText(),
            )
            self._refresh_all()
            self._status("Applied project settings.")
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _on_mode_changed(self, _mode: str) -> None:
        message = self.controller.set_schema_design_mode(self.mode_combo.currentText())
        self._refresh_generator_options()
        self._status(message)

    def _on_add_table(self) -> None:
        try:
            self.controller.add_table(table_name="new_table", row_count=100)
            self._refresh_all()
            self._status("Added table 'new_table'.")
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _on_remove_table(self) -> None:
        table_name = self._selected_table_name()
        if not table_name:
            return
        try:
            self.controller.remove_table(table_name)
            self._refresh_all()
            self._status(f"Removed table '{table_name}'.")
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _on_table_selected(self) -> None:
        self._refresh_generator_options()
        self._refresh_columns_table()
        self._refresh_fk_column_combos()

    def _on_dtype_changed(self, _dtype: str) -> None:
        self._refresh_generator_options()
        self._rebuild_structured_form()

    def _on_generator_changed(self, _generator: str) -> None:
        self._rebuild_structured_form()

    def _refresh_generator_options(self) -> None:
        current = self.col_generator.currentText()
        self.col_generator.blockSignals(True)
        self.col_generator.clear()
        self.col_generator.addItems(self.controller.generator_options_for_dtype(self.col_dtype.currentText(), current_generator=current))
        if current:
            idx = self.col_generator.findText(current)
            if idx >= 0:
                self.col_generator.setCurrentIndex(idx)
        self.col_generator.blockSignals(False)

    def _rebuild_structured_form(self) -> None:
        while self.structured_form_layout.rowCount() > 0:
            self.structured_form_layout.removeRow(0)
        self._form_inputs = {}
        generator = self.col_generator.currentText()
        dtype = self.col_dtype.currentText()
        for field in visible_fields_for(generator, dtype=dtype):
            edit = QLineEdit(self.structured_form_group)
            self._form_inputs[field.field_id] = edit
            label = f"{field.label}{' *' if field.required else ''}"
            self.structured_form_layout.addRow(label, edit)

    def _reload_form_from_params(self) -> None:
        try:
            state = self.controller.split_generator_form_state(
                generator_id=self.col_generator.currentText(),
                dtype=self.col_dtype.currentText(),
                params_json=self.col_params.toPlainText(),
            )
            for field_id, edit in self._form_inputs.items():
                edit.setText(self.controller.format_generator_field_value(
                    field_id,
                    generator_id=self.col_generator.currentText(),
                    dtype=self.col_dtype.currentText(),
                    params=state.known_params,
                ))
            self._status("Reloaded structured form from params JSON.")
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _sync_form_to_params(self) -> None:
        try:
            merged = self.controller.merge_generator_form_values(
                generator_id=self.col_generator.currentText(),
                dtype=self.col_dtype.currentText(),
                params_json=self.col_params.toPlainText(),
                form_values={field_id: edit.text() for field_id, edit in self._form_inputs.items()},
            )
            self.col_params.setPlainText(json.dumps(merged, indent=2, sort_keys=True))
            self._status("Synced structured form to params JSON.")
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _build_column_from_editor(self):  # noqa: ANN201
        min_value = float(self.col_min.text()) if self.col_min.text().strip() else None
        max_value = float(self.col_max.text()) if self.col_max.text().strip() else None
        return self.controller.build_column_spec(
            name=self.col_name.text(),
            dtype=self.col_dtype.currentText(),
            nullable=self.col_nullable.isChecked(),
            primary_key=self.col_pk.isChecked(),
            unique=self.col_unique.isChecked(),
            min_value=min_value,
            max_value=max_value,
            choices_csv=self.col_choices.text(),
            pattern=self.col_pattern.text(),
            generator=self.col_generator.currentText(),
            params_json=self.col_params.toPlainText(),
            depends_on_csv=self.col_depends_on.text(),
        )

    def _on_add_column(self) -> None:
        table_name = self._selected_table_name()
        if not table_name:
            return
        try:
            self.controller.add_column(table_name=table_name, column=self._build_column_from_editor())
            self._refresh_all()
            self._status("Added column.")
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _on_update_column(self) -> None:
        table_name = self._selected_table_name()
        index = self.columns_table.currentIndex()
        if not table_name or not index.isValid():
            return
        original = self.columns_model._rows[index.row()].get("name", "")
        try:
            self.controller.update_column(table_name=table_name, original_name=str(original), column=self._build_column_from_editor())
            self._refresh_all()
            self._status("Updated column.")
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _on_remove_column(self) -> None:
        table_name = self._selected_table_name()
        index = self.columns_table.currentIndex()
        if not table_name or not index.isValid():
            return
        name = str(self.columns_model._rows[index.row()].get("name", ""))
        try:
            self.controller.remove_column(table_name=table_name, column_name=name)
            self._refresh_all()
            self._status("Removed column.")
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _on_column_row_clicked(self) -> None:
        index = self.columns_table.currentIndex()
        if not index.isValid():
            return
        row = self.columns_model._rows[index.row()]
        self.col_name.setText(str(row.get("name", "")))
        self.col_dtype.setCurrentText(str(row.get("dtype", "int")))
        self.col_pk.setChecked(str(row.get("primary_key", "")) in {"True", "true", "1"})
        self.col_nullable.setChecked(str(row.get("nullable", "")) in {"True", "true", "1"})
        self.col_unique.setChecked(str(row.get("unique", "")) in {"True", "true", "1"})
        self.col_generator.setCurrentText(str(row.get("generator", "")))
        self.col_depends_on.setText(str(row.get("depends_on", "")))
        self._reload_form_from_params()

    def _refresh_fk_column_combos(self) -> None:
        child_table = self.fk_child_table.currentText()
        parent_table = self.fk_parent_table.currentText()
        child_cols = self.controller.table_column_names(child_table) if child_table else []
        parent_cols = self.controller.table_column_names(parent_table) if parent_table else []
        self.fk_child_column.clear()
        self.fk_child_column.addItems(child_cols)
        self.fk_parent_column.clear()
        self.fk_parent_column.addItems(parent_cols)

    def _on_add_fk(self) -> None:
        try:
            self.controller.add_foreign_key(
                child_table=self.fk_child_table.currentText(),
                child_column=self.fk_child_column.currentText(),
                parent_table=self.fk_parent_table.currentText(),
                parent_column=self.fk_parent_column.currentText(),
                min_children=self.fk_min_children.value(),
                max_children=self.fk_max_children.value(),
                parent_selection_json=self.fk_parent_selection.toPlainText(),
                child_count_distribution_json=self.fk_child_distribution.toPlainText(),
            )
            self._refresh_all()
            self._status("Added relationship.")
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _on_remove_fk(self) -> None:
        index = self.fk_table.currentIndex()
        if not index.isValid():
            return
        fk_index = int(self.fk_model._rows[index.row()]["index"])
        try:
            self.controller.remove_foreign_key(fk_index)
            self._refresh_all()
            self._status("Removed relationship.")
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _on_fk_row_clicked(self) -> None:
        index = self.fk_table.currentIndex()
        if not index.isValid():
            return
        row = self.fk_model._rows[index.row()]
        self.fk_child_table.setCurrentText(str(row.get("child_table", "")))
        self.fk_parent_table.setCurrentText(str(row.get("parent_table", "")))
        self._refresh_fk_column_combos()
        self.fk_child_column.setCurrentText(str(row.get("child_column", "")))
        self.fk_parent_column.setCurrentText(str(row.get("parent_column", "")))
        self.fk_min_children.setValue(int(row.get("min_children", 1)))
        self.fk_max_children.setValue(int(row.get("max_children", 3)))

    def _on_validate(self) -> None:
        ok, message = self.controller.validate_current()
        self.validation_list.clear()
        self.validation_list.addItem(QListWidgetItem(message))
        if ok:
            self._status("Validation passed.")
        else:
            self._status("Validation failed.")

    def _on_generate_preview(self) -> None:
        try:
            self.controller.generate_preview(row_limit=500)
            self._refresh_preview_combo()
            self._refresh_preview_grid()
            self._status("Generated preview rows.")
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _on_export_csv(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select CSV output folder")
        if not folder:
            return
        try:
            paths = self.controller.export_csv(folder)
            self._status(f"Exported CSV for {len(paths)} table(s).")
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _on_export_sqlite(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Select SQLite output file", "", "SQLite DB (*.db)")
        if not path:
            return
        try:
            counts = self.controller.export_sqlite(path)
            self._status(f"Exported SQLite rows for {len(counts)} table(s).")
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _on_undo(self) -> None:
        if self.controller.undo():
            self._refresh_all()
            self._status("Undo applied.")

    def _on_redo(self) -> None:
        if self.controller.redo():
            self._refresh_all()
            self._status("Redo applied.")

    def _refresh_preview_combo(self) -> None:
        current = self.preview_table_combo.currentText()
        self.preview_table_combo.blockSignals(True)
        self.preview_table_combo.clear()
        self.preview_table_combo.addItems(self.controller.preview_table_names())
        if current:
            idx = self.preview_table_combo.findText(current)
            if idx >= 0:
                self.preview_table_combo.setCurrentIndex(idx)
        self.preview_table_combo.blockSignals(False)

    def _refresh_preview_grid(self) -> None:
        table_name = self.preview_table_combo.currentText()
        rows = self.controller.preview_rows_for_table(table_name) if table_name else []
        self.preview_model.set_rows(rows)

    def _refresh_columns_table(self) -> None:
        table_name = self._selected_table_name()
        rows = self.controller.column_rows(table_name) if table_name else []
        self.columns_model.set_rows(rows, columns=self._column_columns)

    def _refresh_all(self) -> None:
        self.project_name_edit.setText(self.controller.project.name)
        self.seed_spin.setValue(int(self.controller.project.seed))

        mode_idx = self.mode_combo.findText(self.controller.schema_design_mode)
        if mode_idx >= 0:
            self.mode_combo.blockSignals(True)
            self.mode_combo.setCurrentIndex(mode_idx)
            self.mode_combo.blockSignals(False)

        payload = self.controller.project_level_json_text()
        self.timeline_json.setPlainText(payload["timeline_constraints"])
        self.quality_json.setPlainText(payload["data_quality_profiles"])
        self.fits_json.setPlainText(payload["sample_profile_fits"])
        self.locale_json.setPlainText(payload["locale_identity_bundles"])

        selected = self._selected_table_name()
        self.table_list.clear()
        for table_name in self.controller.table_names():
            self.table_list.addItem(QListWidgetItem(table_name))
        if self.table_list.count() > 0:
            target = selected or self.table_list.item(0).text()
            matches = self.table_list.findItems(target, Qt.MatchFlag.MatchExactly)
            self.table_list.setCurrentItem(matches[0] if matches else self.table_list.item(0))

        table_names = self.controller.table_names()
        current_child = self.fk_child_table.currentText()
        current_parent = self.fk_parent_table.currentText()
        self.fk_child_table.clear()
        self.fk_parent_table.clear()
        self.fk_child_table.addItems(table_names)
        self.fk_parent_table.addItems(table_names)
        if current_child:
            idx = self.fk_child_table.findText(current_child)
            if idx >= 0:
                self.fk_child_table.setCurrentIndex(idx)
        if current_parent:
            idx = self.fk_parent_table.findText(current_parent)
            if idx >= 0:
                self.fk_parent_table.setCurrentIndex(idx)

        self._refresh_fk_column_combos()
        self._refresh_generator_options()
        self._rebuild_structured_form()
        self._refresh_columns_table()
        self.fk_model.set_rows(self.controller.foreign_key_rows(), columns=self._fk_columns)
        self._refresh_preview_combo()
        self._refresh_preview_grid()


__all__ = ["ExperimentalSchemaProjectWindow"]
