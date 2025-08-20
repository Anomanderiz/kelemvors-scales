
"""
Kelemvor's Scales — Boss Balance Desktop (Encounter MC + Auto-Tune, Crunchy Crits)
"""

from __future__ import annotations

import json
import math
import os
import random
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QAction, QIcon, QColor
from PySide6.QtWidgets import QToolBar, QStyle, QTableWidgetItem, QWidget, QHBoxLayout, QVBoxLayout, QRadioButton, QButtonGroup, QSizePolicy

# Optional dark theme. Safe no-op if missing.
try:
    import qdarktheme  # type: ignore
except ImportError:
    qdarktheme = None

# Matplotlib in Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

APP_TITLE = "Kelemvor's Scales — Encounter MC + Auto-Tune (Crunchy Crits)"
STATE_FILE = "state.json"  # Autosave target
PROFILE_DIR = Path("./profiles")
PROFILE_DIR.mkdir(parents=True, exist_ok=True)

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

MODERN_QSS = """
QWidget { font-family: 'Inter','Segoe UI',sans-serif; font-size: 11pt; background-color: #1a1b26; color: #c0caf5; }
QMainWindow, QDialog { background-color: #1a1b26; }
QLabel { color: #c0caf5; padding: 2px; }
QPushButton { background-color: #2e3c56; color: #c0caf5; border: 1px solid #414868; padding: 8px 16px; border-radius: 8px; font-weight: bold; }
QPushButton:hover { background-color: #414868; }
QPushButton:pressed { background-color: #2a344e; }
QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #16161e; color: #c0caf5; border: 1px solid #414868; border-radius: 6px; padding: 6px;
}
QTableWidget { background-color: #16161e; gridline-color: #2a344e; border: 1px solid #414868; border-radius: 6px; }
QHeaderView::section { background-color: #24283b; color: #a9b1d6; padding: 8px; border: none; border-bottom: 1px solid #414868; font-weight: bold; }
QTableWidget::item { padding: 4px; }
QTableWidget::item:selected { background-color: #3d59a1; color: #ffffff; }
QTabBar::tab { background: #24283b; color: #a9b1d6; padding: 10px 20px; border-top-left-radius: 8px; border-top-right-radius: 8px; border-bottom: none; font-weight: bold; }
QTabBar::tab:selected { background: #3d59a1; color: #ffffff; }
QTabWidget::pane { border: 1px solid #414868; border-top: none; border-radius: 0 0 8px 8px; }
QToolBar { background: #24283b; border: none; padding: 4px; }
QStatusBar { background: #24283b; color: #a9b1d6; }
QGroupBox { border: 1px solid #414868; border-radius: 8px; margin-top: 10px; padding: 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #a9b1d6; font-weight: bold; }
QSplitter::handle { background-color: #414868; }
QRadioButton { spacing: 5px; }
QCheckBox { spacing: 5px; }
"""

def style_table(table: QtWidgets.QTableWidget):
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
    for r in range(table.rowCount()):
        table.setRowHeight(r, 36)

def load_json(path: str | Path) -> Optional[dict]:
    p = Path(path)
    if not p.exists(): return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return None

def save_json(path: str | Path, data: dict) -> None:
    try:
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
    except IOError:
        pass

def safe_int(x: Any, default: int = 0) -> int:
    try:
        if pd.isna(x): return default
    except Exception: pass
    try:
        return int(x)
    except (ValueError, TypeError):
        try: return int(float(x))
        except (ValueError, TypeError): return default

def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(x): return default
    except Exception: pass
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except (ValueError, TypeError):
        return default

DamageDice = List[Tuple[int, int]]  # [(count, sides)]

def parse_damage_expression(expr: str) -> Tuple[int, DamageDice, int]:
    s = str(expr).strip().lower().replace(" ", "")
    if not s: return 1, [], 0
    sign = -1 if s.startswith("-") else 1
    if s.startswith(("-", "+")): s = s[1:]
    dice_terms = re.findall(r"([+-]?\d*)d(\d+)", s)
    dice: DamageDice = []
    for c_str, sides_str in dice_terms:
        c = 1 if c_str in ("", "+") else (-1 if c_str == "-" else safe_int(c_str, 1))
        dice.append((c, safe_int(sides_str, 0)))
    s_wo = re.sub(r"([+-]?\d*)d\d+", "", s)
    tokens = re.findall(r"[+-]?\d+", s_wo)
    mod = sum(safe_int(t, 0) for t in tokens)
    return sign, dice, mod

def average_damage(expr: str) -> float:
    sign, dice, mod = parse_damage_expression(expr)
    avg = sum(c * (s + 1) / 2.0 for c, s in dice) + mod
    return max(0.0, sign * avg)

def average_crunchy_crit_damage(expr: str) -> float:
    """Crunchy crit = one set of dice at max + one set rolled; modifier once."""
    sign, dice, mod = parse_damage_expression(expr)
    # Expected value for "max + roll" of 1dS is S + (S+1)/2
    avg_dice = sum(c * (s + (s + 1) / 2.0) for c, s in dice)
    return max(0.0, sign * (avg_dice + mod))

def roll_damage(expr: str, size: int = 1) -> np.ndarray:
    sign, dice, mod = parse_damage_expression(expr)
    total_roll = np.zeros(size, dtype=float)
    for count, sides in dice:
        if count == 0 or sides <= 0: continue
        num_rolls = abs(count)
        rolls = np.random.randint(1, sides + 1, size=(num_rolls, size))
        total_roll += np.sign(count) * np.sum(rolls, axis=0)
    total_roll += mod
    total_roll *= sign
    return np.maximum(0.0, total_roll)

def roll_damage_crunchy_crit(expr: str) -> float:
    """Crunchy crit roll: for each die, add max(S) + random(1..S); add modifier once; apply overall sign."""
    sign, dice, mod = parse_damage_expression(expr)
    total = 0.0
    for count, sides in dice:
        if sides <= 0 or count == 0:
            continue
        n = abs(count)
        # one set max, one set rolled
        max_part = n * sides
        roll_part = int(np.random.randint(1, sides + 1, size=n).sum())
        total += math.copysign(max_part + roll_part, count)
    total += mod
    total *= sign
    return max(0.0, total)

SAVE_KEYS = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]

def hit_probs(ac: int, attack_bonus: int, mode: str = "normal") -> Tuple[float, float, float]:
    """Returns (p_noncrit, p_crit, p_any)."""
    def classify(r: int) -> tuple[bool, bool]:
        if r == 1: return (False, False)
        if r == 20: return (True, True)
        return (r + attack_bonus >= ac, False)

    if mode == "normal":
        hits = [classify(r) for r in range(1, 21)]
        p_crit = sum(1 for _, is_crit in hits if is_crit) / 20.0
        p_noncrit = sum(1 for is_hit, is_crit in hits if is_hit and not is_crit) / 20.0
        return p_noncrit, p_crit, p_noncrit + p_crit

    hits = [classify(max(r1, r2) if mode == "adv" else min(r1, r2)) for r1 in range(1, 21) for r2 in range(1, 21)]
    p_crit = sum(1 for _, is_crit in hits if is_crit) / 400.0
    p_noncrit = sum(1 for is_hit, is_crit in hits if is_hit and not is_crit) / 400.0
    return p_noncrit, p_crit, p_noncrit + p_crit

def expected_attack_damage(ac: int, attack_bonus: int, dmg: str, mode: str = "normal") -> float:
    p_noncrit, p_crit, _ = hit_probs(ac, attack_bonus, mode)
    return p_noncrit * average_damage(dmg) + p_crit * average_crunchy_crit_damage(dmg)

def p_save_fail(dc: int, save_bonus: int) -> float:
    target = dc - save_bonus
    if target <= 1: return 1/20.0 # fail only on 1
    if target > 20: return 19/20.0 # succeed only on 20
    return (target - 1) / 20.0

def expected_save_half_damage(dc: int, save_bonus: int, dmg: str) -> float:
    return (0.5 + 0.5 * p_save_fail(dc, save_bonus)) * average_damage(dmg)

def parse_recharge(text: str) -> float:
    t = str(text).strip().replace("–", "-").replace("—", "-")
    if not t: return 0.0
    if "-" in t:
        try:
            lo_s, hi_s = t.split("-", 1)
            lo, hi = int(lo_s), int(hi_s)
            lo, hi = min(lo, hi), max(lo, hi)
            lo = max(1, min(6, lo))
            hi = max(1, min(6, hi))
            return (hi - lo + 1) / 6.0
        except (ValueError, TypeError):
            return 0.0
    try:
        k = int(t); k = max(2, min(6, k))
        return (7 - k) / 6.0
    except (ValueError, TypeError):
        return 0.0

@dataclass
class Attack:
    name: str
    kind: str  # "attack" or "save"
    attack_bonus: int
    dc: int
    save_stat: str
    damage_expr: str
    uses_per_round: int
    is_melee: bool
    enabled: bool

DEFAULT_OPTIONS: Dict[str, Any] = {
    "mode_select": "normal", "spread_targets": 1, "thp_expr": "1d6+4",
    "lair_enabled": False, "lair_avg": 6.0, "lair_targets": 2, "lair_every_n": 2,
    "rech_enabled": False, "recharge_text": "5-6", "rech_avg": 22.0, "rech_targets": 1,
    "rider_mode": "none", "rider_duration": 1, "rider_melee_only": True,
    "boss_hp": 150, "resist_factor": 1.0, "boss_regen": 0.0,
    "mc_rounds": 3, "mc_trials": 10000, "mc_show_hist": True,
    # Encounter MC additions
    "enc_trials": 10000, "enc_max_rounds": 12, "enc_use_nova": False,
    "dpr_cv": 0.60, "initiative_mode": "random",
    # Auto-tuner
    "tune_target_median": 4.0, "tune_tpk_cap": 0.05
}

@dataclass
class AppState:
    party_table: List[dict] = field(default_factory=list)
    attacks_table: List[dict] = field(default_factory=list)
    party_dpr_table: List[dict] = field(default_factory=list)
    party_nova_table: List[dict] = field(default_factory=list)
    options: Dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_OPTIONS))

    def to_profile_dict(self) -> dict:
        return {
            "party_table": self.party_table,
            "attacks_table": self.attacks_table,
            "party_dpr_table": self.party_dpr_table,
            "party_nova_table": self.party_nova_table,
            **self.options,
        }

    @staticmethod
    def from_profile_dict(d: dict) -> "AppState":
        d = d or {}
        party = d.get("party_table") or [
            {"Name": "Fighter", "AC": 18, "HP": 40, "STR": 4, "DEX": 2, "CON": 3, "INT": 0, "WIS": 1, "CHA": 0},
            {"Name": "Rogue", "AC": 16, "HP": 35, "STR": 0, "DEX": 5, "CON": 2, "INT": 1, "WIS": 2, "CHA": 1},
            {"Name": "Cleric", "AC": 19, "HP": 38, "STR": 3, "DEX": 0, "CON": 3, "INT": 1, "WIS": 4, "CHA": 2},
            {"Name": "Wizard", "AC": 13, "HP": 30, "STR": 0, "DEX": 3, "CON": 2, "INT": 5, "WIS": 2, "CHA": 1},
        ]
        attacks = d.get("attacks_table") or [
            {"Name": "Bite", "Type": "attack", "Attack bonus": 7, "DC": 0, "Save": "DEX", "Damage": "2d10+5", "Uses/round": 1, "Melee?": True, "Enabled?": True},
            {"Name": "Claw", "Type": "attack", "Attack bonus": 7, "DC": 0, "Save": "DEX", "Damage": "2d6+5", "Uses/round": 2, "Melee?": True, "Enabled?": True},
            {"Name": "Fire Breath", "Type": "save", "Attack bonus": 0, "DC": 15, "Save": "DEX", "Damage": "8d6", "Uses/round": 1, "Melee?": False, "Enabled?": True},
        ]
        dpr = d.get("party_dpr_table") or [{"Member": "Fighter", "DPR": 15.0}]
        nova = d.get("party_nova_table") or [{"Member": "Fighter", "Nova DPR": 25.0, "Atk Bonus": 8, "Roll Mode": "normal", "Target AC": 17, "Crit Ratio": 1.5, "Uptime": 0.9}]
        opts = {k: d.get(k, v) for k, v in DEFAULT_OPTIONS.items()}
        return AppState(party_table=party, attacks_table=attacks, party_dpr_table=dpr, party_nova_table=nova, options=opts)

class RadioButtonWidget(QWidget):
    def __init__(self, value: bool = True):
        super().__init__()
        layout = QHBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.group = QButtonGroup(self)
        self.rb_true = QRadioButton("Yes"); self.rb_false = QRadioButton("No")
        self.group.addButton(self.rb_true, 1); self.group.addButton(self.rb_false, 0)
        layout.addWidget(self.rb_true); layout.addWidget(self.rb_false)
        self.rb_true.setChecked(value); self.rb_false.setChecked(not value)
    def is_true(self) -> bool: return self.rb_true.isChecked()

def set_table_from_records(table: QtWidgets.QTableWidget, records: List[dict], headers: List[str], bool_cols: List[str] = None):
    bool_cols = bool_cols or []
    table.clear()
    table.setRowCount(0)
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    for r, row_data in enumerate(records):
        table.insertRow(r)
        for c, h in enumerate(headers):
            val = row_data.get(h, "")
            if h in bool_cols:
                widget = RadioButtonWidget(bool(val))
                table.setCellWidget(r, c, widget)
            else:
                item = QTableWidgetItem(str(val))
                if isinstance(val, (int, float)):
                    item.setData(Qt.ItemDataRole.EditRole, val)
                table.setItem(r, c, item)
    style_table(table)

def get_records_from_table(table: QtWidgets.QTableWidget, headers: List[str], bool_cols: List[str] = None) -> List[dict]:
    bool_cols = bool_cols or []
    records: List[dict] = []
    for r in range(table.rowCount()):
        row_data: dict = {}
        is_row_empty = True
        for c, h in enumerate(headers):
            if h in bool_cols:
                widget = table.cellWidget(r, c)
                if isinstance(widget, RadioButtonWidget):
                    row_data[h] = widget.is_true()
                    is_row_empty = False
            else:
                item = table.item(r, c)
                text = item.text() if item else ""
                row_data[h] = text
                if text.strip(): is_row_empty = False
        if not is_row_empty:
            records.append(row_data)
    return records

def attacks_enabled_from_table(tbl: List[dict]) -> List[Attack]:
    return [
        Attack(
            name=str(row.get("Name", "Attack")),
            kind=str(row.get("Type", "attack")).strip().lower(),
            attack_bonus=safe_int(row.get("Attack bonus")),
            dc=safe_int(row.get("DC")),
            save_stat=str(row.get("Save", "DEX")).upper(),
            damage_expr=str(row.get("Damage", "1d6")),
            uses_per_round=max(0, safe_int(row.get("Uses/round"), 1)),
            is_melee=bool(row.get("Melee?", True)),
            enabled=bool(row.get("Enabled?", True)),
        )
        for row in tbl if bool(row.get("Enabled?", True))
    ]

def get_save_bonus(row: dict, stat: str) -> int:
    return safe_int(row.get(stat.upper()))

def per_round_dpr_vs_pc(pc_row: dict, mode: str, attacks_enabled: List[Attack]) -> float:
    ac = safe_int(pc_row.get("AC", 10))
    total_dpr = 0.0
    for atk in attacks_enabled:
        if atk.uses_per_round <= 0: continue
        if atk.kind == "save":
            dpr = expected_save_half_damage(atk.dc, get_save_bonus(pc_row, atk.save_stat), atk.damage_expr)
        else:
            dpr = expected_attack_damage(ac, atk.attack_bonus, atk.damage_expr, mode)
        total_dpr += dpr * atk.uses_per_round
    return total_dpr

def lair_per_target_dpr(options: Dict[str, Any], party_size: int) -> float:
    if not options.get("lair_enabled") or party_size <= 0: return 0.0
    p_hit = min(1.0, float(options.get("lair_targets", 1)) / party_size)
    cadence = max(1, int(options.get("lair_every_n", 1)))
    return (float(options.get("lair_avg", 0.0)) * p_hit) / float(cadence)

def recharge_per_target_dpr(options: Dict[str, Any], party_size: int) -> float:
    if not options.get("rech_enabled") or party_size <= 0: return 0.0
    recharge_prob = parse_recharge(options.get("recharge_text", "5-6"))
    p_hit = min(1.0, float(options.get("rech_targets", 1)) / party_size)
    return recharge_prob * float(options.get("rech_avg", 0.0)) * p_hit

class MplCanvas(FigureCanvas):
    def __init__(self, width=6, height=3.2, dpi=120, dark=False):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.ax = self.fig.add_subplot(111)
        if dark:
            self.fig.patch.set_facecolor("#1a1b26")
            self.ax.set_facecolor("#16161e")
            self.ax.tick_params(axis='x', colors='#c0caf5')
            self.ax.tick_params(axis='y', colors='#c0caf5')
            self.ax.xaxis.label.set_color('#c0caf5')
            self.ax.yaxis.label.set_color('#c0caf5')
            self.ax.title.set_color('#c0caf5')
            for spine in self.ax.spines.values():
                spine.set_edgecolor('#414868')
        super().__init__(self.fig)


        # Make the canvas expand with layouts/splitters
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.updateGeometry()

    def sizeHint(self):
        return QtCore.QSize(900, 360)

    def minimumSizeHint(self):
        return QtCore.QSize(400, 220)
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(1360, 900)

        if qdarktheme: qdarktheme.setup_theme("dark")
        self.setStyleSheet(MODERN_QSS)

        self.app_state = self._load_state()

        self.H_PARTY = ["Name", "AC", "HP", "STR", "DEX", "CON", "INT", "WIS", "CHA"]
        self.H_DPR = ["Member", "DPR"]
        self.H_NOVA = ["Member", "Nova DPR", "Atk Bonus", "Roll Mode", "Target AC", "Crit Ratio", "Uptime"]
        self.H_ATTACKS = ["Name", "Type", "Attack bonus", "DC", "Save", "Damage", "Uses/round", "Melee?", "Enabled?"]

        self.tabs = QtWidgets.QTabWidget(); self.setCentralWidget(self.tabs)
        self._init_party_tab()
        self._init_attacks_tab()
        self._init_det_tab()
        self._init_ttd_tab()
        self._init_mc_tab()
        self._init_encounter_tab()
        self._init_report_tab()

        self._init_menus()
        self._refresh_all_ui()
        self.statusBar().showMessage("Ready.", 3000)

    def _create_button(self, text: str, icon_char: str, tooltip: str, on_click) -> QtWidgets.QPushButton:
        btn = QtWidgets.QPushButton(f" {icon_char} {text}")
        btn.setToolTip(tooltip); btn.clicked.connect(on_click)
        return btn

    def _append_record(self, table: QtWidgets.QTableWidget, headers: List[str], record: dict, bool_cols: List[str] = None):
        bool_cols = bool_cols or []
        r = table.rowCount(); table.insertRow(r)
        for c, h in enumerate(headers):
            val = record.get(h, "")
            if h in bool_cols:
                widget = RadioButtonWidget(bool(val)); table.setCellWidget(r, c, widget)
            else:
                item = QTableWidgetItem(str(val))
                if isinstance(val, (int, float)):
                    item.setData(Qt.ItemDataRole.EditRole, val)
                table.setItem(r, c, item)
        table.setRowHeight(r, 36); table.scrollToBottom()

    def _delete_selected_rows(self, table: QtWidgets.QTableWidget):
        rows = sorted({idx.row() for idx in table.selectedIndexes()}, reverse=True)
        if not rows:
            self.statusBar().showMessage("No rows selected to delete.", 2000); return
        for r in rows: table.removeRow(r)
        self.statusBar().showMessage(f"Deleted {len(rows)} row(s).", 2000)

    def _add_party_row(self): self._append_record(self.tbl_party, self.H_PARTY, {"Name": "New PC", "AC": 16, "HP": 35})
    def _del_party_rows(self): self._delete_selected_rows(self.tbl_party)
    def _add_dpr_row(self): self._append_record(self.tbl_dpr, self.H_DPR, {"Member": "New PC", "DPR": 10.0})
    def _del_dpr_rows(self): self._delete_selected_rows(self.tbl_dpr)
    def _add_nova_row(self): self._append_record(self.tbl_nova, self.H_NOVA, {"Member": "New PC", "Nova DPR": 12.0, "Atk Bonus": 7, "Roll Mode": "normal", "Target AC": 16, "Crit Ratio": 1.5, "Uptime": 0.85})
    def _del_nova_rows(self): self._delete_selected_rows(self.tbl_nova)
    def _add_attack_row(self): self._append_record(self.tbl_attacks, self.H_ATTACKS, {"Name": "New Attack", "Type": "attack", "Attack bonus": 6, "Damage": "1d6+3", "Uses/round": 1, "Melee?": True, "Enabled?": True}, bool_cols=["Melee?", "Enabled?"])
    def _del_attack_rows(self): self._delete_selected_rows(self.tbl_attacks)

    def _load_state(self) -> AppState:
        data = load_json(STATE_FILE)
        return AppState.from_profile_dict(data if data is not None else {})

    def _save_state(self):
        self._pull_all_ui()
        save_json(STATE_FILE, self.app_state.to_profile_dict())
        self.statusBar().showMessage(f"State saved to {STATE_FILE}", 3000)

    def _init_menus(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        acts = {
            "save": ("Save Profile", "Ctrl+S", self._on_save),
            "save_as": ("Save Profile As…", "Ctrl+Shift+S", self._on_save_as),
            "load": ("Load Profile…", "Ctrl+O", self._on_load),
            "quit": ("Quit", "Ctrl+Q", self.close)
        }
        for name, (text, shortcut, handler) in acts.items():
            action = QAction(text, self)
            action.setShortcut(shortcut)
            action.triggered.connect(handler)
            file_menu.addAction(action)
            if name == "load": file_menu.addSeparator()

    def _on_save(self): self._pull_all_ui(); self._save_state()
    def _on_save_as(self):
        self._pull_all_ui()
        name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Profile As", str(PROFILE_DIR / "profile.json"), "JSON (*.json)")
        if name:
            save_json(name, self.app_state.to_profile_dict())
            self.statusBar().showMessage(f"Saved profile to {name}", 3000)
    def _on_load(self):
        name, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load Profile", str(PROFILE_DIR), "JSON (*.json)")
        if name:
            data = load_json(name)
            if data is not None:
                self.app_state = AppState.from_profile_dict(data)
                self._refresh_all_ui()
                self.statusBar().showMessage(f"Loaded profile: {name}", 3000)
            else:
                QtWidgets.QMessageBox.warning(self, "Load Error", f"Could not load or parse the file: {name}")

    def _init_party_tab(self):
        self.tab_party = QWidget()
        layout = QtWidgets.QVBoxLayout(self.tab_party); layout.setSpacing(15)

        party_group = QtWidgets.QGroupBox("Party Composition (AC, HP, Save Bonuses)")
        party_layout = QtWidgets.QVBoxLayout(party_group)
        self.tbl_party = QtWidgets.QTableWidget(); party_layout.addWidget(self.tbl_party)
        party_btns = QHBoxLayout()
        party_btns.addWidget(self._create_button("Add PC", "➕", "Add a new party member", self._add_party_row))
        party_btns.addWidget(self._create_button("Delete PC", "➖", "Delete selected party members", self._del_party_rows))
        party_btns.addStretch(); party_layout.addLayout(party_btns)
        layout.addWidget(party_group)

        sync_reset_layout = QHBoxLayout()
        sync_reset_layout.addWidget(self._create_button("Sync Names to DPR/Nova", "🔄", "Copy PC names to the DPR and Nova tables", self._sync_names))
        sync_reset_layout.addWidget(self._create_button("Reset to Defaults", "🧼", "Reset all party and DPR data to defaults", self._reset_party_defaults))
        sync_reset_layout.addStretch()
        layout.addLayout(sync_reset_layout)

        dpr_nova_splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        dpr_group = QtWidgets.QGroupBox("Manual Effective DPR")
        dpr_layout = QtWidgets.QVBoxLayout(dpr_group)
        self.tbl_dpr = QtWidgets.QTableWidget(); dpr_layout.addWidget(self.tbl_dpr)
        dpr_btns = QHBoxLayout()
        dpr_btns.addWidget(self._create_button("Add", "➕", "Add DPR entry", self._add_dpr_row))
        dpr_btns.addWidget(self._create_button("Delete", "➖", "Delete selected DPR entries", self._del_dpr_rows))
        dpr_btns.addStretch(); dpr_layout.addLayout(dpr_btns)
        dpr_nova_splitter.addWidget(dpr_group)

        nova_group = QtWidgets.QGroupBox("Nova → Effective DPR Conversion")
        nova_layout = QtWidgets.QVBoxLayout(nova_group)
        self.tbl_nova = QtWidgets.QTableWidget(); nova_layout.addWidget(self.tbl_nova)
        nova_btns = QHBoxLayout()
        nova_btns.addWidget(self._create_button("Add", "➕", "Add Nova entry", self._add_nova_row))
        nova_btns.addWidget(self._create_button("Delete", "➖", "Delete selected Nova entries", self._del_nova_rows))
        nova_btns.addStretch(); nova_layout.addLayout(nova_btns)
        dpr_nova_splitter.addWidget(nova_group)
        dpr_nova_splitter.setSizes([self.width() // 2, self.width() // 2])
        layout.addWidget(dpr_nova_splitter)
        self.tabs.addTab(self.tab_party, "👥 Party & DPR")

    def _sync_names(self):
        party = self._records_party()
        names = [r["Name"] for r in party if str(r.get("Name", "")).strip()]
        dpr_map = {r.get("Member"): r for r in self._records_dpr()}
        new_dpr = [{"Member": nm, "DPR": safe_float(dpr_map.get(nm, {}).get("DPR"), 10.0)} for nm in names]
        set_table_from_records(self.tbl_dpr, new_dpr, self.H_DPR)

        nova_map = {r.get("Member"): r for r in self._records_nova()}
        new_nova = [{
            "Member": nm,
            "Nova DPR": safe_float(nova_map.get(nm, {}).get("Nova DPR"), 12.0),
            "Atk Bonus": safe_int(nova_map.get(nm, {}).get("Atk Bonus"), 7),
            "Roll Mode": nova_map.get(nm, {}).get("Roll Mode", "normal"),
            "Target AC": safe_int(nova_map.get(nm, {}).get("Target AC"), 16),
            "Crit Ratio": safe_float(nova_map.get(nm, {}).get("Crit Ratio"), 1.5),
            "Uptime": safe_float(nova_map.get(nm, {}).get("Uptime"), 0.85),
        } for nm in names]
        set_table_from_records(self.tbl_nova, new_nova, self.H_NOVA)
        self.statusBar().showMessage("Synced names to DPR and Nova tables.", 2000)

    def _reset_party_defaults(self):
        reply = QtWidgets.QMessageBox.question(self, "Confirm Reset",
            "Reset all party, DPR, and Nova data to the default template?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No)
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            default_state = AppState.from_profile_dict({})
            self.app_state.party_table = default_state.party_table
            self.app_state.party_dpr_table = default_state.party_dpr_table
            self.app_state.party_nova_table = default_state.party_nova_table
            self._refresh_all_ui()
            self.statusBar().showMessage("Party, DPR, and Nova tables reset to defaults.", 3000)

    def _init_attacks_tab(self):
        self.tab_attacks = QWidget()
        layout = QtWidgets.QVBoxLayout(self.tab_attacks)

        attacks_group = QtWidgets.QGroupBox("Boss Attacks (including Legendary Actions)")
        attacks_layout = QtWidgets.QVBoxLayout(attacks_group)
        self.tbl_attacks = QtWidgets.QTableWidget()
        attacks_layout.addWidget(self.tbl_attacks)
        attack_btns = QHBoxLayout()
        attack_btns.addWidget(self._create_button("Add Attack", "➕", "Add a new attack or save-based action", self._add_attack_row))
        attack_btns.addWidget(self._create_button("Delete Attack", "➖", "Delete selected attacks", self._del_attack_rows))
        attack_btns.addStretch(); attacks_layout.addLayout(attack_btns)
        layout.addWidget(attacks_group)

        extras_group = QtWidgets.QGroupBox("Additional Damage Sources & Effects")
        grid = QtWidgets.QGridLayout(extras_group)

        self.chk_lair = QtWidgets.QCheckBox("Lair Action")
        self.spn_lair_avg = QtWidgets.QDoubleSpinBox(); self.spn_lair_avg.setRange(0, 999)
        self.spn_lair_targets = QtWidgets.QSpinBox(); self.spn_lair_targets.setRange(1, 20)
        self.spn_lair_cadence = QtWidgets.QSpinBox(); self.spn_lair_cadence.setRange(1, 20)
        grid.addWidget(self.chk_lair, 0, 0)
        grid.addWidget(QtWidgets.QLabel("Avg Dmg:"), 0, 1); grid.addWidget(self.spn_lair_avg, 0, 2)
        grid.addWidget(QtWidgets.QLabel("Targets:"), 0, 3); grid.addWidget(self.spn_lair_targets, 0, 4)
        grid.addWidget(QtWidgets.QLabel("Every N rounds:"), 0, 5); grid.addWidget(self.spn_lair_cadence, 0, 6)

        self.chk_rech = QtWidgets.QCheckBox("Recharge Power")
        self.txt_rech_text = QtWidgets.QLineEdit("5-6")
        self.spn_rech_avg = QtWidgets.QDoubleSpinBox(); self.spn_rech_avg.setRange(0, 999)
        self.spn_rech_targets = QtWidgets.QSpinBox(); self.spn_rech_targets.setRange(1, 20)
        grid.addWidget(self.chk_rech, 1, 0)
        grid.addWidget(QtWidgets.QLabel("Recharge (e.g., 5-6):"), 1, 1); grid.addWidget(self.txt_rech_text, 1, 2)
        grid.addWidget(QtWidgets.QLabel("Avg Dmg:"), 1, 3); grid.addWidget(self.spn_rech_avg, 1, 4)
        grid.addWidget(QtWidgets.QLabel("Targets:"), 1, 5); grid.addWidget(self.spn_rech_targets, 1, 6)

        rider_group = QtWidgets.QGroupBox("On-Hit Rider Effect (for Monte-Carlo)")
        rider_layout = QHBoxLayout(rider_group)
        self.cmb_rider = QtWidgets.QComboBox()
        self.cmb_rider.addItems(["none", "grant advantage on melee next round", "-2 AC next round"])
        self.spn_rider_duration = QtWidgets.QSpinBox(); self.spn_rider_duration.setRange(1, 10)
        self.chk_rider_melee_only = QtWidgets.QCheckBox("Melee Only?")
        rider_layout.addWidget(QtWidgets.QLabel("Effect:"))
        rider_layout.addWidget(self.cmb_rider, 1)
        rider_layout.addWidget(QtWidgets.QLabel("Duration (rds):"))
        rider_layout.addWidget(self.spn_rider_duration)
        rider_layout.addWidget(self.chk_rider_melee_only)
        rider_layout.addStretch()

        layout.addWidget(extras_group)
        layout.addWidget(rider_group)
        layout.addStretch(1)
        self.tabs.addTab(self.tab_attacks, "🧰 Boss Kit")

    def _init_det_tab(self):
        self.tab_det = QWidget()
        layout = QtWidgets.QVBoxLayout(self.tab_det)

        controls_group = QtWidgets.QGroupBox("Calculation Parameters")
        controls = QHBoxLayout(controls_group)
        self.cmb_mode = QtWidgets.QComboBox(); self.cmb_mode.addItems(["normal", "adv", "dis"])
        self.spn_spread = QtWidgets.QSpinBox(); self.spn_spread.setRange(1, 20)
        self.txt_thp = QtWidgets.QLineEdit("1d6+4")
        controls.addWidget(QtWidgets.QLabel("Boss Roll Mode:")); controls.addWidget(self.cmb_mode)
        controls.addWidget(QtWidgets.QLabel("Spread Attacks Across:")); controls.addWidget(self.spn_spread); controls.addWidget(QtWidgets.QLabel("Targets"))
        controls.addWidget(QtWidgets.QLabel("Per-Target THP/rd:")); controls.addWidget(self.txt_thp)
        controls.addStretch()
        controls.addWidget(self._create_button("Compute", "📊", "Run deterministic calculation", self._on_compute_deterministic))
        layout.addWidget(controls_group)

        split = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        self.tbl_det = QtWidgets.QTableWidget()
        self.canvas_det = MplCanvas(dark=True)
        self.canvas_det.setMinimumHeight(260)
        split.addWidget(self.tbl_det); split.addWidget(self.canvas_det); split.setStretchFactor(0, 1); split.setStretchFactor(1, 2); split.setSizes([self.height() // 2, self.height() // 2])
        layout.addWidget(split)
        self.tabs.addTab(self.tab_det, "📈 Deterministic DPR")

    def _init_ttd_tab(self):
        self.tab_ttd = QWidget()
        layout = QtWidgets.QVBoxLayout(self.tab_ttd)

        main_splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        controls_widget = QWidget(); controls_layout = QtWidgets.QVBoxLayout(controls_widget)

        boss_group = QtWidgets.QGroupBox("Boss Stats")
        grid = QtWidgets.QGridLayout(boss_group)
        self.spn_boss_hp = QtWidgets.QSpinBox(); self.spn_boss_hp.setRange(1, 9999); self.spn_boss_hp.setValue(150)
        self.dsp_resist = QtWidgets.QDoubleSpinBox(); self.dsp_resist.setRange(0.0, 3.0); self.dsp_resist.setSingleStep(0.1); self.dsp_resist.setValue(1.0)
        self.dsp_regen = QtWidgets.QDoubleSpinBox(); self.dsp_regen.setRange(0.0, 999.0); self.dsp_regen.setSingleStep(1.0)
        grid.addWidget(QtWidgets.QLabel("Boss HP:"), 0, 0); grid.addWidget(self.spn_boss_hp, 0, 1)
        grid.addWidget(QtWidgets.QLabel("Resistance Factor:"), 1, 0); grid.addWidget(self.dsp_resist, 1, 1)
        grid.addWidget(QtWidgets.QLabel("Regen/THP per round:"), 2, 0); grid.addWidget(self.dsp_regen, 2, 1)
        controls_layout.addWidget(boss_group)

        mode_group = QtWidgets.QGroupBox("DPR Input Mode")
        mode_layout = QVBoxLayout(mode_group)
        self.grp_mode = QButtonGroup(self)
        r_manual = QRadioButton("Use Manual Effective DPR"); r_nova = QRadioButton("Convert from Nova DPR")
        r_manual.setChecked(True)
        self.grp_mode.addButton(r_manual, 0); self.grp_mode.addButton(r_nova, 1)
        mode_layout.addWidget(r_manual); mode_layout.addWidget(r_nova)
        controls_layout.addWidget(mode_group)

        controls_layout.addWidget(self._create_button("Compute Time-To-Die", "⏳", "Calculate boss TTD based on current settings", self._on_compute_ttd))

        results_group = QtWidgets.QGroupBox("Results")
        results_layout = QVBoxLayout(results_group)
        self.lbl_incoming = QtWidgets.QLabel("<strong>Effective Incoming DPR:</strong> 0.00")
        self.lbl_rounds_exact = QtWidgets.QLabel("<strong>Exact Rounds to Zero:</strong> ∞")
        self.lbl_rounds_ceil = QtWidgets.QLabel("<strong>Boss Defeated In (Rounds):</strong> ∞")
        results_layout.addWidget(self.lbl_incoming); results_layout.addWidget(self.lbl_rounds_exact); results_layout.addWidget(self.lbl_rounds_ceil)
        controls_layout.addWidget(results_group)
        controls_layout.addStretch()

        self.tbl_eff = QtWidgets.QTableWidget()
        main_splitter.addWidget(controls_widget); main_splitter.addWidget(self.tbl_eff)
        main_splitter.setSizes([self.width() // 3, 2 * self.width() // 3])
        layout.addWidget(main_splitter)
        self.tabs.addTab(self.tab_ttd, "⏳ Boss TTD")

    def _init_mc_tab(self):
        self.tab_mc = QWidget()
        layout = QtWidgets.QVBoxLayout(self.tab_mc)

        controls_group = QtWidgets.QGroupBox("Simulation Parameters")
        top = QHBoxLayout(controls_group)
        self.cmb_mc_target = QtWidgets.QComboBox(); top.addWidget(QtWidgets.QLabel("Target PC:")); top.addWidget(self.cmb_mc_target, 1)
        self.spn_mc_rounds = QtWidgets.QSpinBox(); self.spn_mc_rounds.setRange(1, 50); self.spn_mc_rounds.setValue(3)
        self.spn_mc_trials = QtWidgets.QSpinBox(); self.spn_mc_trials.setRange(1000, 200000); self.spn_mc_trials.setSingleStep(1000); self.spn_mc_trials.setValue(10000)
        self.chk_mc_hist = QtWidgets.QCheckBox("Show Histogram"); self.chk_mc_hist.setChecked(True)
        top.addWidget(QtWidgets.QLabel("Rounds:")); top.addWidget(self.spn_mc_rounds)
        top.addWidget(QtWidgets.QLabel("Trials:")); top.addWidget(self.spn_mc_trials)
        top.addWidget(self.chk_mc_hist); top.addStretch()
        top.addWidget(self._create_button("Run Simulation", "🎲", "Run Monte-Carlo simulation (boss damage vs single PC)", self._on_run_mc))
        layout.addWidget(controls_group)

        split = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        results_group = QtWidgets.QGroupBox("Simulation Results")
        toplyt = QtWidgets.QVBoxLayout(results_group)
        self.lbl_mc_mean = QtWidgets.QLabel("<strong>Mean Total Damage:</strong> —")
        self.lbl_mc_p95 = QtWidgets.QLabel("<strong>95th Percentile:</strong> —")
        self.lbl_mc_p99 = QtWidgets.QLabel("<strong>99th Percentile:</strong> —")
        toplyt.addWidget(self.lbl_mc_mean); toplyt.addWidget(self.lbl_mc_p95); toplyt.addWidget(self.lbl_mc_p99)
        self.canvas_mc = MplCanvas(dark=True, height=3.6)
        self.canvas_mc.setMinimumHeight(260)
        split.addWidget(results_group); split.addWidget(self.canvas_mc); split.setStretchFactor(0, 0); split.setStretchFactor(1, 1); split.setSizes([150, 450])
        layout.addWidget(split)
        self.tabs.addTab(self.tab_mc, "🎯 Boss→PC MC")

    def _init_encounter_tab(self):
        self.tab_enc = QWidget()
        layout = QtWidgets.QVBoxLayout(self.tab_enc)

        cfg = QtWidgets.QGroupBox("Encounter Simulation Parameters")
        g = QtWidgets.QGridLayout(cfg)

        self.spn_enc_trials = QtWidgets.QSpinBox(); self.spn_enc_trials.setRange(1000, 300000); self.spn_enc_trials.setSingleStep(1000)
        self.spn_enc_rounds = QtWidgets.QSpinBox(); self.spn_enc_rounds.setRange(1, 50)
        self.dsp_dpr_cv = QtWidgets.QDoubleSpinBox(); self.dsp_dpr_cv.setDecimals(2); self.dsp_dpr_cv.setRange(0.05, 2.00); self.dsp_dpr_cv.setSingleStep(0.05)
        self.cmb_initiative = QtWidgets.QComboBox(); self.cmb_initiative.addItems(["random", "party_first", "boss_first"])

        self.grp_enc_mode = QButtonGroup(self)
        r1 = QRadioButton("Use Manual Effective DPR"); r2 = QRadioButton("Use Nova→Effective DPR")
        r1.setChecked(True); self.grp_enc_mode.addButton(r1, 0); self.grp_enc_mode.addButton(r2, 1)

        g.addWidget(QtWidgets.QLabel("Trials:"), 0, 0); g.addWidget(self.spn_enc_trials, 0, 1)
        g.addWidget(QtWidgets.QLabel("Max Rounds:"), 0, 2); g.addWidget(self.spn_enc_rounds, 0, 3)
        g.addWidget(QtWidgets.QLabel("Party DPR CV (variance):"), 1, 0); g.addWidget(self.dsp_dpr_cv, 1, 1)
        g.addWidget(QtWidgets.QLabel("Initiative:"), 1, 2); g.addWidget(self.cmb_initiative, 1, 3)
        g.addWidget(r1, 2, 0, 1, 2); g.addWidget(r2, 2, 2, 1, 2)
        layout.addWidget(cfg)

        # Auto-Tune controls
        tuner = QtWidgets.QGroupBox("Auto-Tune (HP)")
        tg = QtWidgets.QGridLayout(tuner)
        self.dsp_tune_median = QtWidgets.QDoubleSpinBox(); self.dsp_tune_median.setRange(1.0, 20.0); self.dsp_tune_median.setSingleStep(0.1)
        self.dsp_tune_tpk = QtWidgets.QDoubleSpinBox(); self.dsp_tune_tpk.setRange(0.0, 1.0); self.dsp_tune_tpk.setDecimals(3); self.dsp_tune_tpk.setSingleStep(0.01)
        tg.addWidget(QtWidgets.QLabel("Target median TTK (rounds):"), 0, 0); tg.addWidget(self.dsp_tune_median, 0, 1)
        tg.addWidget(QtWidgets.QLabel("TPK cap (probability):"), 0, 2); tg.addWidget(self.dsp_tune_tpk, 0, 3)
        btns = QHBoxLayout()
        btns.addWidget(self._create_button("Run Encounter Simulation", "⚔️", "Simulate full fights (boss vs party)", self._on_run_encounter))
        btns.addStretch()
        btns.addWidget(self._create_button("Auto‑Tune HP", "🛠️", "Adjust boss HP to hit median TTK (and respect TPK cap if feasible)", self._on_auto_tune))
        layout.addWidget(tuner)
        layout.addLayout(btns)

        split = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        topbox = QtWidgets.QGroupBox("Outcome Summary")
        v = QVBoxLayout(topbox)
        self.lbl_ttk_median = QtWidgets.QLabel("<strong>Median TTK:</strong> —")
        self.lbl_ttk_p1090 = QtWidgets.QLabel("<strong>TTK p10–p90:</strong> —")
        self.lbl_tpk = QtWidgets.QLabel("<strong>TPK Probability:</strong> —")
        self.lbl_downs = QtWidgets.QLabel("<strong>PCs down at victory (mean / p90):</strong> —")
        v.addWidget(self.lbl_ttk_median); v.addWidget(self.lbl_ttk_p1090); v.addWidget(self.lbl_tpk); v.addWidget(self.lbl_downs)

        self.canvas_surv = MplCanvas(dark=True, height=3.2)
        self.canvas_surv.setMinimumHeight(260)
        self.canvas_ttk = MplCanvas(dark=True, height=3.2)
        self.canvas_ttk.setMinimumHeight(280)
        split.addWidget(topbox); split.addWidget(self.canvas_surv); split.addWidget(self.canvas_ttk)
        split.setStretchFactor(0, 0); split.setStretchFactor(1, 1); split.setStretchFactor(2, 1); split.setSizes([140, 360, 360])
        layout.addWidget(split)

        self.tabs.addTab(self.tab_enc, "⚔️ Encounter MC")

    def _init_report_tab(self):
        self.tab_report = QWidget()
        layout = QtWidgets.QVBoxLayout(self.tab_report)
        self.txt_report = QtWidgets.QPlainTextEdit(); self.txt_report.setReadOnly(True); self.txt_report.setFont(QFont("Courier New", 10))
        layout.addWidget(self.txt_report)
        layout.addWidget(self._create_button("Export Profile to JSON", "💾", "Save the current configuration to a JSON file", self._on_export_json))
        self.tabs.addTab(self.tab_report, "🧾 Report")

    def _refresh_all_ui(self):
        set_table_from_records(self.tbl_party, self.app_state.party_table, self.H_PARTY)
        set_table_from_records(self.tbl_dpr, self.app_state.party_dpr_table, self.H_DPR)
        set_table_from_records(self.tbl_nova, self.app_state.party_nova_table, self.H_NOVA)
        set_table_from_records(self.tbl_attacks, self.app_state.attacks_table, self.H_ATTACKS, bool_cols=["Melee?", "Enabled?"])

        o = self.app_state.options
        self.cmb_mode.setCurrentText(o.get("mode_select", "normal"))
        self.spn_spread.setValue(o.get("spread_targets", 1))
        self.txt_thp.setText(o.get("thp_expr", "1d6+4"))
        self.chk_lair.setChecked(o.get("lair_enabled", False))
        self.spn_lair_avg.setValue(o.get("lair_avg", 6.0))
        self.spn_lair_targets.setValue(o.get("lair_targets", 2))
        self.spn_lair_cadence.setValue(o.get("lair_every_n", 2))
        self.chk_rech.setChecked(o.get("rech_enabled", False))
        self.txt_rech_text.setText(str(o.get("recharge_text", "5-6")))
        self.spn_rech_avg.setValue(o.get("rech_avg", 22.0))
        self.spn_rech_targets.setValue(o.get("rech_targets", 1))
        self.cmb_rider.setCurrentText(o.get("rider_mode", "none"))
        self.spn_rider_duration.setValue(o.get("rider_duration", 1))
        self.chk_rider_melee_only.setChecked(o.get("rider_melee_only", True))

        self.spn_boss_hp.setValue(o.get("boss_hp", 150))
        self.dsp_resist.setValue(o.get("resist_factor", 1.0))
        self.dsp_regen.setValue(o.get("boss_regen", 0.0))

        self._refresh_mc_targets()
        self.spn_mc_rounds.setValue(o.get("mc_rounds", 3))
        self.spn_mc_trials.setValue(o.get("mc_trials", 10000))
        self.chk_mc_hist.setChecked(o.get("mc_show_hist", True))

        self.spn_enc_trials.setValue(o.get("enc_trials", 10000))
        self.spn_enc_rounds.setValue(o.get("enc_max_rounds", 12))
        self.dsp_dpr_cv.setValue(o.get("dpr_cv", 0.60))
        self.cmb_initiative.setCurrentText(o.get("initiative_mode", "random"))
        if o.get("enc_use_nova", False): self.grp_enc_mode.button(1).setChecked(True)
        else: self.grp_enc_mode.button(0).setChecked(True)

        self.dsp_tune_median.setValue(o.get("tune_target_median", 4.0))
        self.dsp_tune_tpk.setValue(o.get("tune_tpk_cap", 0.05))

        self._refresh_report_text()

    def _pull_all_ui(self):
        self.app_state.party_table = [{**r, "AC": safe_int(r.get("AC"), 10), "HP": safe_int(r.get("HP"), 1), **{k: safe_int(r.get(k)) for k in SAVE_KEYS}} for r in self._records_party()]
        self.app_state.party_dpr_table = [{**r, "DPR": safe_float(r.get("DPR"))} for r in self._records_dpr()]
        self.app_state.party_nova_table = [{
            **r,
            "Nova DPR": safe_float(r.get("Nova DPR")),
            "Atk Bonus": safe_int(r.get("Atk Bonus")),
            "Roll Mode": str(r.get("Roll Mode", "normal")).strip().lower() or "normal",
            "Target AC": safe_int(r.get("Target AC"), 10),
            "Crit Ratio": safe_float(r.get("Crit Ratio"), 1.5),
            "Uptime": max(0.0, min(1.0, safe_float(r.get("Uptime"), 0.85))),
        } for r in self._records_nova()]

        self.app_state.attacks_table = [{
            **r,
            "Type": (r.get("Type", "attack") or "attack").strip().lower(),
            "Attack bonus": safe_int(r.get("Attack bonus")),
            "DC": safe_int(r.get("DC")),
            "Save": (r.get("Save", "DEX") or "DEX").upper(),
            "Uses/round": safe_int(r.get("Uses/round"), 1),
        } for r in self._records_attacks()]

        o = self.app_state.options
        o.update({
            "mode_select": self.cmb_mode.currentText(), "spread_targets": self.spn_spread.value(),
            "thp_expr": self.txt_thp.text().strip() or "0", "lair_enabled": self.chk_lair.isChecked(),
            "lair_avg": self.spn_lair_avg.value(), "lair_targets": self.spn_lair_targets.value(),
            "lair_every_n": self.spn_lair_cadence.value(), "rech_enabled": self.chk_rech.isChecked(),
            "recharge_text": self.txt_rech_text.text().strip() or "5-6", "rech_avg": self.spn_rech_avg.value(),
            "rech_targets": self.spn_rech_targets.value(), "rider_mode": self.cmb_rider.currentText(),
            "rider_duration": self.spn_rider_duration.value(), "rider_melee_only": self.chk_rider_melee_only.isChecked(),
            "boss_hp": self.spn_boss_hp.value(), "resist_factor": self.dsp_resist.value(),
            "boss_regen": self.dsp_regen.value(), "mc_rounds": self.spn_mc_rounds.value(),
            "mc_trials": self.spn_mc_trials.value(), "mc_show_hist": self.chk_mc_hist.isChecked(),
            "enc_trials": self.spn_enc_trials.value(), "enc_max_rounds": self.spn_enc_rounds.value(),
            "dpr_cv": self.dsp_dpr_cv.value(), "initiative_mode": self.cmb_initiative.currentText(),
            "enc_use_nova": (self.grp_enc_mode.checkedId() == 1),
            "tune_target_median": self.dsp_tune_median.value(), "tune_tpk_cap": self.dsp_tune_tpk.value(),
        })
        self._refresh_report_text()

    def _records_party(self): return get_records_from_table(self.tbl_party, self.H_PARTY)
    def _records_dpr(self): return get_records_from_table(self.tbl_dpr, self.H_DPR)
    def _records_nova(self): return get_records_from_table(self.tbl_nova, self.H_NOVA)
    def _records_attacks(self): return get_records_from_table(self.tbl_attacks, self.H_ATTACKS, bool_cols=["Melee?", "Enabled?"])

    def _on_compute_deterministic(self):
        self._pull_all_ui()
        party = self.app_state.party_table
        attacks_enabled = attacks_enabled_from_table(self.app_state.attacks_table)
        lair_dpr = lair_per_target_dpr(self.app_state.options, len(party) or 1)
        rech_dpr = recharge_per_target_dpr(self.app_state.options, len(party) or 1)
        additive_dpr = lair_dpr + rech_dpr
        thp_avg = max(0.0, average_damage(self.app_state.options.get("thp_expr", "0")))

        rows = []
        for pc in party:
            base_dpr = per_round_dpr_vs_pc(pc, self.app_state.options.get("mode_select", "normal"), attacks_enabled)
            spread_k = float(max(1, self.app_state.options.get("spread_targets", 1)))
            total_dpr = base_dpr / spread_k + additive_dpr
            net_dpr = max(0.0, total_dpr - thp_avg)
            hp = safe_int(pc.get("HP"), 1)
            r_exact = hp / net_dpr if net_dpr > 0 else float("inf")
            rows.append({
                "Name": pc.get("Name", "?"), "AC": pc.get("AC", 10), "HP": hp,
                "DPR (attacks)": round(base_dpr / spread_k, 2),
                "DPR (total)": round(total_dpr, 2),
                "Net DPR (after THP)": round(net_dpr, 2),
                "Rounds to 0 (exact)": f"{r_exact:.2f}" if math.isfinite(r_exact) else "∞",
                "Rounds to 0 (ceil)": int(math.ceil(r_exact)) if math.isfinite(r_exact) else "∞",
            })

        headers = ["Name", "AC", "HP", "DPR (attacks)", "DPR (total)", "Net DPR (after THP)", "Rounds to 0 (exact)", "Rounds to 0 (ceil)"]
        set_table_from_records(self.tbl_det, rows, headers)

        self.canvas_det.ax.clear()
        labels = [r["Name"] for r in rows]
        vals = [r["Rounds to 0 (ceil)"] if r["Rounds to 0 (ceil)"] != "∞" else np.nan for r in rows]
        self.canvas_det.ax.bar(labels, vals)
        self.canvas_det.ax.set_ylabel("Rounds to 0 (Ceiling)", color='#c0caf5')
        self.canvas_det.ax.set_title("Time-To-Zero per Party Member", color='#c0caf5')
        self.canvas_det.ax.tick_params(axis='x', colors='#c0caf5'); self.canvas_det.ax.tick_params(axis='y', colors='#c0caf5')
        self.canvas_det.ax.grid(True, axis='y', linestyle='--', alpha=0.3)
        self.canvas_det.fig.tight_layout(); self.canvas_det.draw()
        self.statusBar().showMessage("Deterministic calculation complete.", 2000)

    def _on_compute_ttd(self):
        self._pull_all_ui()
        use_nova = (self.grp_mode.checkedId() == 1)
        resist = self.app_state.options.get("resist_factor", 1.0)
        regen = self.app_state.options.get("boss_regen", 0.0)

        total_dpr = 0.0; eff_rows = []
        if use_nova:
            for r in self.app_state.party_nova_table:
                nova_dpr = safe_float(r.get("Nova DPR"))
                ab, ac = safe_int(r.get("Atk Bonus")), safe_int(r.get("Target AC"))
                mode, crit_r, uptime = r.get("Roll Mode", "normal"), safe_float(r.get("Crit Ratio"), 1.5), safe_float(r.get("Uptime"), 0.85)
                p_non, p_crit, p_any = hit_probs(ac, ab, mode)
                factor = (p_non + crit_r * p_crit) * uptime
                eff_dpr = nova_dpr * factor
                total_dpr += eff_dpr
                eff_rows.append({"Member": r.get("Member", "?"), "P(any hit)%": f"{100*p_any:.1f}", "P(crit)%": f"{100*p_crit:.1f}", "Factor": f"{factor:.3f}", "Eff DPR": f"{eff_dpr:.2f}"})
            set_table_from_records(self.tbl_eff, eff_rows, ["Member", "P(any hit)%", "P(crit)%", "Factor", "Eff DPR"])
        else:
            total_dpr = sum(safe_float(r.get("DPR")) for r in self.app_state.party_dpr_table)
            set_table_from_records(self.tbl_eff, self.app_state.party_dpr_table, self.H_DPR)

        effective_dpr = max(0.0, total_dpr / resist - regen)
        boss_hp = self.app_state.options.get("boss_hp", 150)
        r_exact = boss_hp / effective_dpr if effective_dpr > 0 else float("inf")
        self.lbl_incoming.setText(f"<strong>Effective Incoming DPR:</strong> {effective_dpr:.2f}")
        self.lbl_rounds_exact.setText(f"<strong>Exact Rounds to Zero:</strong> {'∞' if math.isinf(r_exact) else f'{r_exact:.2f}'}")
        self.lbl_rounds_ceil.setText(f"<strong>Boss Defeated In (Rounds):</strong> {'∞' if math.isinf(r_exact) else int(math.ceil(r_exact))}")
        self.statusBar().showMessage("TTD calculation complete.", 2000)

    def _refresh_mc_targets(self, preserve_name: str | None = None):
        names = [r.get("Name", "PC") for r in self.app_state.party_table if r.get("Name")]
        current = preserve_name or (self.cmb_mc_target.currentText() if self.cmb_mc_target.count() > 0 else None)
        self.cmb_mc_target.blockSignals(True); self.cmb_mc_target.clear(); self.cmb_mc_target.addItems(names or ["(No PCs)"])
        if current in names: self.cmb_mc_target.setCurrentText(current)
        self.cmb_mc_target.blockSignals(False)

    def _on_run_mc(self):
        self._pull_all_ui()
        target_name = self.cmb_mc_target.currentText()
        pc_row = next((r for r in self.app_state.party_table if r.get("Name") == target_name), None)
        if not pc_row:
            QtWidgets.QMessageBox.warning(self, "No Target", "Select a valid party member to run the simulation."); return
        o = self.app_state.options; attacks = attacks_enabled_from_table(self.app_state.attacks_table)
        totals = self._run_mc_sim(pc_row, attacks, o)
        mean, p95, p99 = np.mean(totals), np.percentile(totals, 95), np.percentile(totals, 99)
        self.lbl_mc_mean.setText(f"<strong>Mean Total Damage:</strong> {mean:.1f}")
        self.lbl_mc_p95.setText(f"<strong>95th Percentile:</strong> {p95:.1f}")
        self.lbl_mc_p99.setText(f"<strong>99th Percentile:</strong> {p99:.1f}")

        if o.get("mc_show_hist", True):
            self.canvas_mc.ax.clear()
            self.canvas_mc.ax.hist(totals, bins=50, density=True, alpha=0.85)
            self.canvas_mc.ax.axvline(mean, linestyle="--", label=f"Mean: {mean:.1f}")
            self.canvas_mc.ax.axvline(p95, linestyle=":", label=f"95th: {p95:.1f}")
            self.canvas_mc.ax.axvline(p99, linestyle=":", label=f"99th: {p99:.1f}")
            self.canvas_mc.ax.set_xlabel(f"Total Damage over {o['mc_rounds']} Rounds vs {target_name}", color='#c0caf5')
            self.canvas_mc.ax.set_ylabel("Probability Density", color='#c0caf5')
            self.canvas_mc.ax.set_title("Monte-Carlo Damage Distribution", color='#c0caf5')
            legend = self.canvas_mc.ax.legend()
            for text in legend.get_texts(): text.set_color('#c0caf5')
            legend.get_frame().set_facecolor('#24283b'); legend.get_frame().set_edgecolor('#414868')
            self.canvas_mc.ax.grid(True, axis='y', linestyle='--', alpha=0.3)
            self.canvas_mc.fig.tight_layout(); self.canvas_mc.draw()
        self.statusBar().showMessage(f"Monte-Carlo simulation ({o['mc_trials']} trials) complete.", 3000)

    def _run_mc_sim(self, pc_row: dict, attacks: List[Attack], opts: Dict) -> np.ndarray:
        trials = opts['mc_trials']; rounds = opts['mc_rounds']
        ac = safe_int(pc_row.get("AC", 10))
        save_bonuses = {k: safe_int(pc_row.get(k, 0)) for k in SAVE_KEYS}
        thp_avg = average_damage(opts['thp_expr'])
        total_damage = np.zeros(trials); rider_remaining = np.zeros(trials, dtype=int)

        for _ in range(rounds):
            round_damage = np.zeros(trials); triggered_rider = np.zeros(trials, dtype=bool)
            current_ac = np.full(trials, ac); current_mode = np.full(trials, opts['mode_select'])
            if opts['rider_mode'] == "-2 AC next round": current_ac[rider_remaining > 0] -= 2
            if opts['rider_mode'] == "grant advantage on melee next round": current_mode[rider_remaining > 0] = "adv"

            for atk in attacks:
                if atk.uses_per_round <= 0: continue
                hits_on_target = np.random.binomial(atk.uses_per_round, 1.0 / max(1, opts['spread_targets']), trials)
                for i in range(trials):
                    if hits_on_target[i] == 0: continue
                    if atk.kind == "save":
                        bonus = save_bonuses.get(atk.save_stat.upper(), 0)
                        rolls = np.random.randint(1, 21, hits_on_target[i])
                        successes = (rolls + bonus) >= atk.dc
                        dmg_rolls = roll_damage(atk.damage_expr, hits_on_target[i])
                        round_damage[i] += np.sum(np.where(successes, 0.5 * dmg_rolls, dmg_rolls))
                    else:
                        for _ in range(hits_on_target[i]):
                            r1, r2 = random.randint(1, 20), random.randint(1, 20)
                            roll = r1
                            if current_mode[i] == 'adv': roll = max(r1, r2)
                            if current_mode[i] == 'dis': roll = min(r1, r2)
                            is_crit = (roll == 20)
                            is_hit = is_crit or (roll != 1 and roll + atk.attack_bonus >= current_ac[i])
                            if is_hit:
                                dmg = roll_damage_crunchy_crit(atk.damage_expr) if is_crit else roll_damage(atk.damage_expr, 1)[0]
                                round_damage[i] += dmg
                                if atk.is_melee or not opts['rider_melee_only']: triggered_rider[i] = True

            total_damage += np.maximum(0, round_damage - thp_avg)
            rider_remaining -= 1; rider_remaining[triggered_rider] = opts['rider_duration']
            np.maximum(0, rider_remaining, out=rider_remaining)
        return total_damage

    def _eff_party_dprs(self, use_nova: bool) -> List[Tuple[str, float]]:
        if use_nova:
            res = []
            for r in self.app_state.party_nova_table:
                nova_dpr = safe_float(r.get("Nova DPR"))
                ab, ac = safe_int(r.get("Atk Bonus")), safe_int(r.get("Target AC"))
                mode, crit_r, uptime = r.get("Roll Mode", "normal"), safe_float(r.get("Crit Ratio"), 1.5), safe_float(r.get("Uptime"), 0.85)
                p_non, p_crit, _ = hit_probs(ac, ab, mode)
                factor = (p_non + crit_r * p_crit) * uptime
                res.append((r.get("Member", "?"), nova_dpr * factor))
            return res
        else:
            return [(r.get("Member", "?"), safe_float(r.get("DPR"))) for r in self.app_state.party_dpr_table]

    @staticmethod
    def _gamma_rng(mean: float, cv: float) -> float:
        mean = max(0.0, float(mean)); cv = max(1e-6, float(cv))
        if mean <= 0.0: return 0.0
        k = 1.0 / (cv ** 2); theta = mean / k
        return float(np.random.gamma(k, theta))

    def _on_run_encounter(self):
        self._pull_all_ui()
        metrics = self._run_encounter_mc()
        if metrics is None: return

        ttk = metrics["ttk"]; ttk_alive = ttk[np.isfinite(ttk)]
        if ttk_alive.size == 0:
            QtWidgets.QMessageBox.warning(self, "No Outcome", "Boss never died within the max round cap. Increase Max Rounds."); return

        tpk_prob = metrics["tpk_prob"]; pcs_down = metrics["pcs_down_at_victory"]
        p10, med, p90 = np.percentile(ttk_alive, [10, 50, 90])
        self.lbl_ttk_median.setText(f"<strong>Median TTK:</strong> {med:.2f} rounds")
        self.lbl_ttk_p1090.setText(f"<strong>TTK p10–p90:</strong> {p10:.2f} – {p90:.2f} rounds")
        self.lbl_tpk.setText(f"<strong>TPK Probability:</strong> {100*tpk_prob:.1f}%")
        self.lbl_downs.setText(f"<strong>PCs down at victory:</strong> mean {np.mean(pcs_down):.2f}, p90 {np.percentile(pcs_down,90):.0f}")

        self.canvas_surv.ax.clear()
        times = metrics["times"]; surv = metrics["survival_curve"]
        self.canvas_surv.ax.step(times, surv, where="post")
        self.canvas_surv.ax.set_ylim(0, 1.0)
        self.canvas_surv.ax.set_xlabel("Rounds", color="#c0caf5")
        self.canvas_surv.ax.set_ylabel("S(t): Boss alive probability", color="#c0caf5")
        self.canvas_surv.ax.set_title("Boss Survival Curve", color="#c0caf5")
        self.canvas_surv.ax.grid(True, axis='y', linestyle='--', alpha=0.3)
        self.canvas_surv.fig.tight_layout(); self.canvas_surv.draw()

        self.canvas_ttk.ax.clear()
        self.canvas_ttk.ax.hist(ttk_alive, bins=40, density=True, alpha=0.85)
        self.canvas_ttk.ax.axvline(med, linestyle="--", label=f"Median: {med:.2f}")
        self.canvas_ttk.ax.set_xlabel("Rounds to boss defeat", color="#c0caf5")
        self.canvas_ttk.ax.set_ylabel("Probability Density", color="#c0caf5")
        self.canvas_ttk.ax.set_title("TTK Distribution", color="#c0caf5")
        leg = self.canvas_ttk.ax.legend()
        for text in leg.get_texts(): text.set_color('#c0caf5')
        leg.get_frame().set_facecolor('#24283b'); leg.get_frame().set_edgecolor('#414868')
        self.canvas_ttk.ax.grid(True, axis='y', linestyle='--', alpha=0.3)
        self.canvas_ttk.fig.tight_layout(); self.canvas_ttk.draw()
        self.statusBar().showMessage(f"Encounter simulation complete. Trials={len(ttk)}", 4000)

    def _run_encounter_mc(self) -> Optional[dict]:
        o = self.app_state.options
        party = list(self.app_state.party_table)
        if not party:
            QtWidgets.QMessageBox.warning(self, "No Party", "Add at least one party member in the Party tab."); return None
        attacks = attacks_enabled_from_table(self.app_state.attacks_table)
        if not attacks and not (o.get("lair_enabled") or o.get("rech_enabled")):
            QtWidgets.QMessageBox.warning(self, "No Boss Offense", "Enable at least one boss attack, lair action, or recharge power."); return None

        trials = int(o.get("enc_trials", 10000))
        max_rounds = int(o.get("enc_max_rounds", 12))
        resist = float(o.get("resist_factor", 1.0))
        regen = float(o.get("boss_regen", 0.0))
        thp_avg = max(0.0, average_damage(o.get("thp_expr", "0")))
        spread_targets = max(1, int(o.get("spread_targets", 1)))
        init_mode = str(o.get("initiative_mode", "random"))
        use_nova = bool(o.get("enc_use_nova", False))
        dpr_cv = float(o.get("dpr_cv", 0.60))

        eff_list = self._eff_party_dprs(use_nova)
        if not eff_list:
            QtWidgets.QMessageBox.warning(self, "No DPR", "Provide DPR (manual or nova→eff) for at least one party member."); return None

        party_names = [r.get("Name", f"PC{i+1}") for i, r in enumerate(party)]
        P = len(party_names)
        eff_by_name = dict(eff_list)
        eff_means = np.array([eff_by_name.get(nm, 0.0) for nm in party_names], dtype=float)

        boss_hp0 = float(o.get("boss_hp", 150))
        trials_idx = np.arange(trials)
        boss_hp = np.full(trials, boss_hp0, dtype=float)
        pcs_hp = np.zeros((trials, P), dtype=float); pcs_alive = np.ones((trials, P), dtype=bool)
        for j, pc in enumerate(party): pcs_hp[:, j] = float(safe_int(pc.get("HP", 1)))

        pc_AC = np.array([safe_int(pc.get("AC", 10)) for pc in party], dtype=int)
        pc_saves = np.array([[safe_int(pc.get(k, 0)) for k in SAVE_KEYS] for pc in party], dtype=int)
        save_index = {k: i for i, k in enumerate(SAVE_KEYS)}
        rider_rem = np.zeros((trials, P), dtype=int)

        ttk = np.full(trials, np.inf, dtype=float)
        tpk_flags = np.zeros(trials, dtype=bool)
        pcs_down_at_victory = np.zeros(trials, dtype=int)

        def boss_goes_first(n: int) -> np.ndarray:
            if init_mode == "boss_first": return np.ones(n, dtype=bool)
            if init_mode == "party_first": return np.zeros(n, dtype=bool)
            return np.random.rand(n) < 0.5

        for rnd in range(1, max_rounds + 1):
            ongoing = ~np.isfinite(ttk)
            if not ongoing.any(): break

            boss_first_flags = boss_goes_first(trials)

            mask_party_first = ongoing & (~boss_first_flags)
            if mask_party_first.any():
                dmg_party = np.zeros(trials, dtype=float)
                for j in range(P):
                    alive_mask = mask_party_first & pcs_alive[:, j]
                    if not alive_mask.any(): continue
                    means = eff_means[j]
                    draws = np.array([self._gamma_rng(means, dpr_cv) for _ in range(int(alive_mask.sum()))], dtype=float)
                    dmg_party[alive_mask] += draws
                dmg_party = np.maximum(0.0, dmg_party / max(1e-6, resist) - regen)
                boss_hp[mask_party_first] -= dmg_party[mask_party_first]
                newly_dead = (boss_hp <= 0) & mask_party_first & (~np.isfinite(ttk))
                ttk[newly_dead] = rnd
                pcs_down_at_victory[newly_dead] = (pcs_alive[newly_dead] == False).sum(axis=1)

            ongoing = ~np.isfinite(ttk)
            if ongoing.any():
                current_ac = np.tile(pc_AC, (trials, 1))
                current_mode = np.full((trials, P), o['mode_select'], dtype=object)
                rider_mode = o.get('rider_mode', 'none')
                if rider_mode == "-2 AC next round":
                    current_ac[rider_rem > 0] = np.maximum(1, current_ac[rider_rem > 0] - 2)
                if rider_mode == "grant advantage on melee next round":
                    current_mode[rider_rem > 0] = "adv"
                rider_trig = np.zeros((trials, P), dtype=bool)
                # Build per-trial target pools for this round (uniform over all living PCs)
                round_pool = [None] * trials
                for t in np.where(ongoing)[0]:
                    alive = np.where(pcs_alive[t])[0]
                    if alive.size == 0:
                        continue
                    k = min(spread_targets, alive.size)
                    # sample without replacement among all living PCs
                    round_pool[t] = np.random.choice(alive, size=k, replace=False)

                for atk in attacks:
                    if atk.uses_per_round <= 0: continue
                    for use in range(atk.uses_per_round):
                        for t in np.where(ongoing)[0]:
                            pool = round_pool[t]
                            if pool is None or len(pool) == 0:
                                continue  # no living PCs in this trial

                            # In-case someone died earlier this round, intersect with current alive
                            alive_pool = [idx for idx in pool if pcs_alive[t, idx]]
                            if not alive_pool:
                                # fallback to any currently-alive PC
                                alive_now = np.where(pcs_alive[t])[0]
                                if alive_now.size == 0:
                                    continue
                                alive_pool = alive_now

                            target = int(np.random.choice(alive_pool))

                            if not pcs_alive[t, target]: continue
                            if atk.kind == "save":
                                bonus = pc_saves[target, save_index[atk.save_stat.upper()]]
                                roll = random.randint(1, 20)
                                success = (roll == 20) or (roll + bonus >= atk.dc and roll != 1)
                                dmg = float(roll_damage(atk.damage_expr, 1)[0])
                                dealt = 0.5 * dmg if success else dmg
                            else:
                                r1, r2 = random.randint(1, 20), random.randint(1, 20)
                                mode = current_mode[t, target]
                                r = r1
                                if mode == "adv": r = max(r1, r2)
                                if mode == "dis": r = min(r1, r2)
                                is_crit = (r == 20)
                                is_hit = is_crit or (r != 1 and r + atk.attack_bonus >= current_ac[t, target])
                                if not is_hit:
                                    dealt = 0.0
                                else:
                                    dealt = roll_damage_crunchy_crit(atk.damage_expr) if is_crit else float(roll_damage(atk.damage_expr, 1)[0])
                                    if atk.is_melee or not o.get('rider_melee_only', True):
                                        rider_trig[t, target] = True
                            dealt = max(0.0, dealt - thp_avg)
                            pcs_hp[t, target] -= dealt
                            if pcs_hp[t, target] <= 0 and pcs_alive[t, target]:
                                pcs_alive[t, target] = False

                # Lair
                if o.get("lair_enabled", False) and (rnd % max(1, int(o.get("lair_every_n", 1))) == 0):
                    L = int(o.get("lair_targets", 1)); avg = float(o.get("lair_avg", 0.0))
                    for t in np.where(ongoing)[0]:
                        alive_idxs = np.where(pcs_alive[t])[0]
                        if alive_idxs.size == 0: continue
                        choose = min(L, alive_idxs.size); targets = np.random.choice(alive_idxs, size=choose, replace=False)
                        for idx in targets:
                            dealt = self._gamma_rng(avg, 0.50)
                            dealt = max(0.0, dealt - thp_avg)
                            pcs_hp[t, idx] -= dealt
                            if pcs_hp[t, idx] <= 0 and pcs_alive[t, idx]: pcs_alive[t, idx] = False

                # Recharge
                if o.get("rech_enabled", False):
                    p_rech = parse_recharge(o.get("recharge_text", "5-6")); R = int(o.get("rech_targets", 1)); avg = float(o.get("rech_avg", 0.0))
                    for t in np.where(ongoing)[0]:
                        if random.random() < p_rech:
                            alive_idxs = np.where(pcs_alive[t])[0]
                            if alive_idxs.size == 0: continue
                            choose = min(R, alive_idxs.size); targets = np.random.choice(alive_idxs, size=choose, replace=False)
                            for idx in targets:
                                dealt = self._gamma_rng(avg, 0.50)
                                dealt = max(0.0, dealt - thp_avg)
                                pcs_hp[t, idx] -= dealt
                                if pcs_hp[t, idx] <= 0 and pcs_alive[t, idx]: pcs_alive[t, idx] = False

                rider_rem = np.maximum(0, rider_rem - 1); rider_rem[rider_trig] = int(o.get("rider_duration", 1))
                none_alive = pcs_alive.sum(axis=1) == 0
                new_tpk = ongoing & none_alive
                tpk_flags[new_tpk] = True

            ongoing = ~np.isfinite(ttk)
            mask_party_after = ongoing & boss_first_flags
            if mask_party_after.any():
                dmg_party = np.zeros(trials, dtype=float)
                for j in range(P):
                    alive_mask = mask_party_after & pcs_alive[:, j]
                    if not alive_mask.any(): continue
                    means = eff_means[j]
                    draws = np.array([self._gamma_rng(means, dpr_cv) for _ in range(int(alive_mask.sum()))], dtype=float)
                    dmg_party[alive_mask] += draws
                dmg_party = np.maximum(0.0, dmg_party / max(1e-6, resist) - regen)
                boss_hp[mask_party_after] -= dmg_party[mask_party_after]
                newly_dead = (boss_hp <= 0) & mask_party_after & (~np.isfinite(ttk))
                ttk[newly_dead] = rnd
                pcs_down_at_victory[newly_dead] = (pcs_alive[newly_dead] == False).sum(axis=1)

        times = np.arange(0, max_rounds + 1)
        surv = np.empty_like(times, dtype=float)
        for i, t in enumerate(times): surv[i] = np.mean((ttk > t))

        return {
            "ttk": ttk,
            "tpk_prob": float(np.mean(tpk_flags)),
            "pcs_down_at_victory": pcs_down_at_victory[np.isfinite(ttk)],
            "times": times,
            "survival_curve": surv,
        }

    def _on_auto_tune(self):
        self._pull_all_ui()
        o = self.app_state.options
        target = float(o.get("tune_target_median", 4.0))
        tpk_cap = float(o.get("tune_tpk_cap", 0.05))
        original_hp = float(o.get("boss_hp", 150))
        original_trials = int(o.get("enc_trials", 10000))

        def simulate_with_hp(hp: float, trials: int) -> Tuple[float, float]:
            o["boss_hp"] = int(max(1, round(hp)))
            o["enc_trials"] = int(trials)
            metrics = self._run_encounter_mc()
            if metrics is None:
                return math.inf, 1.0
            ttk = metrics["ttk"]; ttk_alive = ttk[np.isfinite(ttk)]
            if ttk_alive.size == 0:  # boss never dies
                return math.inf, float(metrics["tpk_prob"])
            med = float(np.median(ttk_alive))
            return med, float(metrics["tpk_prob"])

        self.statusBar().showMessage("Auto‑tuning HP…", 2000)
        # Bracket search
        quick_trials = max(3000, int(original_trials * 0.4))
        low, high = 1.0, max(10.0, original_hp)
        med_low, tpk_low = simulate_with_hp(low, quick_trials)
        med_high, tpk_high = simulate_with_hp(high, quick_trials)

        # Ensure high median >= target by escalating high
        attempts = 0
        while med_high < target and attempts < 12:
            high *= 2.0
            med_high, tpk_high = simulate_with_hp(high, quick_trials)
            attempts += 1

        if med_low > target:
            # Even minimal HP exceeds target; try lower
            low = 1.0
            med_low, tpk_low = simulate_with_hp(low, quick_trials)

        if not (med_low <= target <= med_high):
            QtWidgets.QMessageBox.warning(self, "Auto‑Tune Warning",
                "Could not bracket the target median TTK by adjusting HP alone. "
                "Try increasing Max Rounds or adjusting party/boss parameters.")
            # Restore
            o["boss_hp"] = int(original_hp); o["enc_trials"] = original_trials
            return

        # Bisection on HP for median TTK
        for _ in range(16):
            mid = 0.5 * (low + high)
            med_mid, _tpk_mid = simulate_with_hp(mid, quick_trials)
            if med_mid >= target:
                high = mid; med_high = med_mid
            else:
                low = mid; med_low = med_mid
            if abs(med_mid - target) < 0.05:
                break

        tuned_hp = int(round(high))
        # Final full simulation
        o["boss_hp"] = tuned_hp; o["enc_trials"] = original_trials
        metrics = self._run_encounter_mc()
        if metrics is None:
            QtWidgets.QMessageBox.warning(self, "Auto‑Tune Error", "Failed to simulate with tuned parameters.")
            o["boss_hp"] = int(original_hp); o["enc_trials"] = original_trials; return

        ttk = metrics["ttk"]; ttk_alive = ttk[np.isfinite(ttk)]
        med = float(np.median(ttk_alive)) if ttk_alive.size else math.inf
        tpk = float(metrics["tpk_prob"])

        # Update UI
        self.spn_boss_hp.setValue(int(tuned_hp))
        self.lbl_ttk_median.setText(f"<strong>Median TTK:</strong> {med:.2f} rounds")
        self.lbl_tpk.setText(f"<strong>TPK Probability:</strong> {100*tpk:.1f}%")
        self.statusBar().showMessage(f"Auto‑tune complete. Boss HP set to {tuned_hp}. Median≈{med:.2f}, TPK={100*tpk:.1f}%.", 6000)

        if tpk > tpk_cap + 1e-9:
            QtWidgets.QMessageBox.information(self, "TPK Cap Not Met",
                f"The tuned HP achieves median≈{med:.2f} rounds but TPK={100*tpk:.1f}% exceeds your cap of {100*tpk_cap:.1f}%.\n\n"
                "HP alone can’t reduce lethality without shortening the fight. Consider reducing boss DPR "
                "(fewer attacks, lower attack bonus, lower damage dice) or adding party sustain.")

        # Restore trials to original
        o["enc_trials"] = original_trials

        # Refresh charts/labels
        self._on_run_encounter()

    def _refresh_report_text(self):
        self.txt_report.setPlainText(json.dumps(self.app_state.to_profile_dict(), indent=2))

    def _on_export_json(self):
        self._pull_all_ui()
        name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export Profile JSON", str(PROFILE_DIR / "current_profile.json"), "JSON (*.json)")
        if name:
            save_json(name, self.app_state.to_profile_dict())
            self.statusBar().showMessage(f"Exported profile to {name}", 3000)

    def closeEvent(self, event):
        self._save_state()
        super().closeEvent(event)

def set_table_from_records(table: QtWidgets.QTableWidget, records: List[dict], headers: List[str], bool_cols: List[str] = None):
    # (Override shadowing earlier def, kept here for safety in PyInstaller single-file)
    bool_cols = bool_cols or []
    table.clear(); table.setRowCount(0); table.setColumnCount(len(headers)); table.setHorizontalHeaderLabels(headers)
    for r, row_data in enumerate(records):
        table.insertRow(r)
        for c, h in enumerate(headers):
            val = row_data.get(h, "")
            if h in bool_cols:
                widget = RadioButtonWidget(bool(val)); table.setCellWidget(r, c, widget)
            else:
                item = QTableWidgetItem(str(val))
                if isinstance(val, (int, float)): item.setData(Qt.ItemDataRole.EditRole, val)
                table.setItem(r, c, item)
    style_table(table)

def main():
    app = QtWidgets.QApplication([])
    icon_path = resource_path("Untitled design (1).ico")
    if os.path.exists(icon_path): app.setWindowIcon(QIcon(icon_path))
    win = MainWindow(); win.show(); app.exec()

if __name__ == "__main__":
    main()
