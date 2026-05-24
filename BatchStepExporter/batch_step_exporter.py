import csv
import itertools
import os
import re

import FreeCAD as App
import FreeCADGui as Gui
import ImportGui
from PySide import QtGui, QtCore


ICON_XPM = """
/* XPM */
static char * xpm[] = {
"16 16 3 1",
"  c None",
". c #1E90FF",
"+ c #0C3B66",
"                ",
"   ++++++++     ",
"   +......+     ",
"   +......+     ",
"   +......+     ",
"   ++++++++     ",
"   ++++++++     ",
"   +......+     ",
"   +......+     ",
"   +......+     ",
"   ++++++++     ",
"                ",
"      ++++      ",
"      +..+      ",
"      ++++      ",
"                "
};
"""

ICON_PATH = os.path.join(os.path.dirname(__file__), "Resources", "icons", "BatchStepExporter.svg")

RANGE_RE = re.compile(
    r"^\s*(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)(?:\s*:\s*(-?\d+(?:\.\d+)?))?\s*$"
)
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


class ParameterSpec(object):
    def __init__(self, sheet_name, alias, values, unit=""):
        self.sheet_name = sheet_name
        self.alias = alias
        self.values = values
        self.unit = unit.strip()


def sanitize_name(text):
    clean = SAFE_NAME_RE.sub("_", text.strip())
    clean = clean.strip("_")
    return clean or "item"


def format_number(value):
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return ("%f" % value).rstrip("0").rstrip(".")


def parse_value_expression(expr):
    parts = [p.strip() for p in expr.split(",") if p.strip()]
    if not parts:
        raise ValueError("Werte-Feld ist leer.")

    resolved = []
    for token in parts:
        match = RANGE_RE.match(token)
        if not match:
            resolved.append(token)
            continue

        start = float(match.group(1))
        end = float(match.group(2))
        step_text = match.group(3)
        if step_text is None:
            step = 1.0 if end >= start else -1.0
        else:
            step = float(step_text)

        if step == 0:
            raise ValueError("Range-Schritt darf nicht 0 sein: %s" % token)
        if start < end and step < 0:
            raise ValueError("Range fuer %s braucht positiven Schritt." % token)
        if start > end and step > 0:
            raise ValueError("Range fuer %s braucht negativen Schritt." % token)

        current = start
        epsilon = abs(step) / 100000.0
        if step > 0:
            while current <= end + epsilon:
                resolved.append(format_number(current))
                current += step
        else:
            while current >= end - epsilon:
                resolved.append(format_number(current))
                current += step

    return resolved


def get_spreadsheets(doc):
    return [obj for obj in doc.Objects if obj.TypeId == "Spreadsheet::Sheet"]


def get_bodies(doc, include_hidden):
    bodies = []
    for obj in doc.Objects:
        if obj.TypeId != "PartDesign::Body":
            continue

        if include_hidden:
            bodies.append(obj)
            continue

        visible = True
        if hasattr(obj, "ViewObject") and obj.ViewObject is not None:
            visible = bool(getattr(obj.ViewObject, "Visibility", True))
        if visible:
            bodies.append(obj)

    return bodies


def apply_value_to_alias(doc, sheet_name, alias, raw_value, unit):
    sheet = doc.getObject(sheet_name)
    if sheet is None:
        raise ValueError("Spreadsheet nicht gefunden: %s" % sheet_name)

    try:
        cell = sheet.getCellFromAlias(alias)
    except Exception:
        raise ValueError("Alias '%s' nicht in Spreadsheet '%s' gefunden." % (alias, sheet_name))

    value_text = str(raw_value).strip()
    if unit:
        value_text = "%s %s" % (value_text, unit)

    sheet.set(cell, value_text)


def write_iteration_manifest(path, param_pairs):
    with open(path, "w") as handle:
        for key, value in param_pairs:
            handle.write("%s=%s\n" % (key, value))


def get_project_name(doc):
    file_name = getattr(doc, "FileName", "")
    if file_name:
        base = os.path.splitext(os.path.basename(file_name))[0]
    else:
        base = getattr(doc, "Label", "") or getattr(doc, "Name", "") or "project"
    return sanitize_name(base)


def run_export(doc, export_root, run_prefix, include_hidden, parameter_specs):
    if doc is None:
        raise ValueError("Kein aktives Dokument offen.")

    if not parameter_specs:
        raise ValueError("Mindestens ein Parameter ist erforderlich.")

    bodies = get_bodies(doc, include_hidden)
    if not bodies:
        raise ValueError("Keine Bodies im Dokument gefunden.")

    os.makedirs(export_root, exist_ok=True)

    value_lists = [spec.values for spec in parameter_specs]
    combinations = list(itertools.product(*value_lists))
    if not combinations:
        raise ValueError("Keine Kombinationen erzeugt.")

    project_name = get_project_name(doc)

    summary_rows = []

    for index, combo in enumerate(combinations, start=1):
        aliases_with_values = []
        folder_parts = []

        for spec, value in zip(parameter_specs, combo):
            apply_value_to_alias(doc, spec.sheet_name, spec.alias, value, spec.unit)
            aliases_with_values.append((spec.alias, value))
            folder_parts.append("%s_%s" % (sanitize_name(spec.alias), sanitize_name(str(value))))

        doc.recompute()

        folder_name = "_".join(folder_parts) if folder_parts else "export"
        iteration_dir = os.path.join(export_root, folder_name)
        if os.path.exists(iteration_dir):
            iteration_dir = os.path.join(export_root, "%s__it_%03d" % (folder_name, index))
        os.makedirs(iteration_dir, exist_ok=True)

        manifest_path = os.path.join(iteration_dir, "iteration_values.txt")
        write_iteration_manifest(manifest_path, aliases_with_values)

        part_name_counts = {}
        for body in bodies:
            base_part_name = sanitize_name(body.Label or body.Name)
            current_count = part_name_counts.get(base_part_name, 0) + 1
            part_name_counts[base_part_name] = current_count

            if current_count == 1:
                part_name = base_part_name
            else:
                part_name = "%s_%02d" % (base_part_name, current_count)

            step_name = "%03d_%s_%s.step" % (index, project_name, part_name)
            step_path = os.path.join(iteration_dir, step_name)
            ImportGui.export([body], step_path)

        summary = {"iteration": index, "folder": iteration_dir}
        for alias, value in aliases_with_values:
            summary[alias] = value
        summary_rows.append(summary)

    csv_path = os.path.join(export_root, "export_summary.csv")
    all_keys = ["iteration", "folder"]
    for spec in parameter_specs:
        if spec.alias not in all_keys:
            all_keys.append(spec.alias)

    with open(csv_path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=all_keys)
        writer.writeheader()
        for row in summary_rows:
            writer.writerow(row)

    return {
        "iterations": len(combinations),
        "bodies": len(bodies),
        "root": export_root,
        "summary_csv": csv_path,
    }


class ExportDialog(QtGui.QDialog):
    def __init__(self, doc, parent=None):
        super(ExportDialog, self).__init__(parent)
        self.doc = doc
        self.spreadsheets = get_spreadsheets(doc)
        self.setWindowTitle("Batch STEP Exporter")
        self.resize(900, 560)
        self._build_ui()

    def _build_ui(self):
        layout = QtGui.QVBoxLayout(self)

        info = QtGui.QLabel(
            "Definiere Parameterzeilen als: Tabelle + Alias + Werte.\n"
            "Werte unterstuetzen Listen (4,6,8), Ranges (4-20) und Ranges mit Schritt (4-20:2)."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QtGui.QFormLayout()

        self.export_dir_edit = QtGui.QLineEdit(os.path.join(os.path.expanduser("~"), "freecad_exports"))
        browse_button = QtGui.QPushButton("Browse...")
        browse_button.clicked.connect(self._choose_export_dir)
        dir_row = QtGui.QHBoxLayout()
        dir_row.addWidget(self.export_dir_edit)
        dir_row.addWidget(browse_button)
        form.addRow("Export root:", dir_row)

        self.include_hidden_cb = QtGui.QCheckBox("Include hidden bodies")
        self.include_hidden_cb.setChecked(False)
        form.addRow("", self.include_hidden_cb)

        layout.addLayout(form)

        self.param_table = QtGui.QTableWidget(0, 4)
        self.param_table.setHorizontalHeaderLabels(["Spreadsheet", "Alias", "Werte", "Einheit (optional)"])
        self.param_table.horizontalHeader().setStretchLastSection(True)
        self.param_table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        layout.addWidget(self.param_table)

        button_row = QtGui.QHBoxLayout()
        add_row_btn = QtGui.QPushButton("Add row")
        add_row_btn.clicked.connect(self._add_row)
        remove_row_btn = QtGui.QPushButton("Remove selected row")
        remove_row_btn.clicked.connect(self._remove_selected_row)
        button_row.addWidget(add_row_btn)
        button_row.addWidget(remove_row_btn)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self._add_row(default_alias="te", default_values="4-20")

        box = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel)
        box.accepted.connect(self._on_confirm)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

    def _choose_export_dir(self):
        selected = QtGui.QFileDialog.getExistingDirectory(self, "Waehle Export-Verzeichnis")
        if selected:
            self.export_dir_edit.setText(selected)

    def _new_sheet_combo(self):
        combo = QtGui.QComboBox()
        for sheet in self.spreadsheets:
            combo.addItem(sheet.Name)
        return combo

    def _add_row(self, default_alias="", default_values="", default_unit=""):
        row = self.param_table.rowCount()
        self.param_table.insertRow(row)

        sheet_combo = self._new_sheet_combo()
        self.param_table.setCellWidget(row, 0, sheet_combo)

        alias_item = QtGui.QTableWidgetItem(default_alias)
        values_item = QtGui.QTableWidgetItem(default_values)
        unit_item = QtGui.QTableWidgetItem(default_unit)

        self.param_table.setItem(row, 1, alias_item)
        self.param_table.setItem(row, 2, values_item)
        self.param_table.setItem(row, 3, unit_item)

    def _remove_selected_row(self):
        indexes = self.param_table.selectionModel().selectedRows()
        if not indexes:
            return
        for idx in sorted([i.row() for i in indexes], reverse=True):
            self.param_table.removeRow(idx)

    def _parse_parameter_specs(self):
        specs = []
        for row in range(self.param_table.rowCount()):
            sheet_combo = self.param_table.cellWidget(row, 0)
            alias_item = self.param_table.item(row, 1)
            values_item = self.param_table.item(row, 2)
            unit_item = self.param_table.item(row, 3)

            sheet_name = sheet_combo.currentText().strip() if sheet_combo else ""
            alias = alias_item.text().strip() if alias_item else ""
            values_expr = values_item.text().strip() if values_item else ""
            unit = unit_item.text().strip() if unit_item else ""

            if not sheet_name and not alias and not values_expr:
                continue
            if not sheet_name:
                raise ValueError("Zeile %d: Spreadsheet fehlt." % (row + 1))
            if not alias:
                raise ValueError("Zeile %d: Alias fehlt." % (row + 1))
            if not values_expr:
                raise ValueError("Zeile %d: Werte fehlen." % (row + 1))

            specs.append(ParameterSpec(sheet_name, alias, parse_value_expression(values_expr), unit))

        return specs

    def _on_confirm(self):
        try:
            export_root = self.export_dir_edit.text().strip()
            if not export_root:
                raise ValueError("Export root darf nicht leer sein.")

            include_hidden = self.include_hidden_cb.isChecked()
            specs = self._parse_parameter_specs()

            result = run_export(
                self.doc,
                export_root=export_root,
                run_prefix="",
                include_hidden=include_hidden,
                parameter_specs=specs,
            )

            QtGui.QMessageBox.information(
                self,
                "Export abgeschlossen",
                "Iterationen: {iterations}\nBodies je Iteration: {bodies}\nRoot: {root}\nCSV: {summary_csv}".format(**result),
            )
            self.accept()
        except Exception as exc:
            QtGui.QMessageBox.critical(self, "Fehler", str(exc))


class BatchStepExportCommand(object):
    def GetResources(self):
        return {
            "Pixmap": ICON_PATH,
            "MenuText": "Batch STEP Export",
            "ToolTip": "Iterate spreadsheet aliases, recompute and export all bodies as STEP",
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        doc = App.ActiveDocument
        dialog = ExportDialog(doc, Gui.getMainWindow())
        dialog.exec_()


def register_command():
    existing = []
    try:
        existing = Gui.listCommands()
    except Exception:
        pass

    if "BatchStepExport" in existing:
        return

    Gui.addCommand("BatchStepExport", BatchStepExportCommand())
