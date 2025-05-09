#!/usr/bin/env python

import sys
import subprocess
import shlex
import configparser
from pathlib import Path
import os
import re

from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QColorDialog, QFrame, QSizePolicy, QMessageBox, QGridLayout
)
from PyQt6.QtGui import QColor, QPalette, QFont
from PyQt6.QtCore import Qt, QSize

# --- Constants ---
HELPER_SCRIPT_PATH = "/usr/local/bin/omen-rgb-helper.sh"
CONFIG_DIR = Path.home() / ".config" / "omenrgbgui"
CONFIG_FILE = CONFIG_DIR / "settings.ini"
SYSFS_RGB_BASE_PATH = Path("/sys/devices/platform/hp-wmi/rgb_zones")

class OmenRgbGui(QWidget):
    def __init__(self):
        super().__init__()
        self.current_color = QColor("white") # Default/fallback color
        self.target_zone = "all"             # Default target zone

        self.load_settings()
        self.init_ui()
        self.update_ui_from_loaded_settings()

    def _get_sysfs_path_for_zone(self, zone_id_str: str) -> Path | None:
        """Helper to construct the sysfs path for a given zone ID string."""
        if not zone_id_str.isdigit():
            return None
        zone_num = int(zone_id_str)
        # Format zone number as two hex digits (e.g., 0 -> 00, 1 -> 01)
        zone_hex_str = f"{zone_num:02X}"
        return SYSFS_RGB_BASE_PATH / f"zone{zone_hex_str}_rgb"

    def _query_color_from_sysfs_for_zone(self, zone_id_str: str) -> QColor | None:
        """
        Tries to read and parse the color for a specific zone_id_str from sysfs.
        Returns a QColor object or None if unsuccessful.
        """
        sysfs_file_path = self._get_sysfs_path_for_zone(zone_id_str)
        if not sysfs_file_path:
            print(f"Cannot determine sysfs path for zone ID '{zone_id_str}'.")
            return None

        try:
            with open(sysfs_file_path, 'r') as f:
                content = f.read().strip()
                match = re.search(r'([0-9a-fA-F]{6})', content)
                if match:
                    hex_color = match.group(1)
                    parsed_qcolor = QColor(f"#{hex_color}")
                    if parsed_qcolor.isValid():
                        print(f"Successfully queried color for zone {zone_id_str} from {sysfs_file_path}: {parsed_qcolor.name()}")
                        return parsed_qcolor
                    else:
                        print(f"Sysfs for zone {zone_id_str} gave invalid hex '#{hex_color}' from content '{content}'.")
                else:
                    print(f"Could not parse hex color from sysfs content for zone {zone_id_str}: '{content}'.")
        except FileNotFoundError:
            print(f"Sysfs file for zone {zone_id_str} not found: {sysfs_file_path}.")
        except PermissionError:
            print(f"Permission denied reading sysfs file for zone {zone_id_str}: {sysfs_file_path}. "
                  "GUI needs read access or helper script modification for this feature.")
        except Exception as e:
            print(f"Error reading color for zone {zone_id_str} from sysfs ({sysfs_file_path}): {e}")
        return None

    def ensure_config_dir_exists(self):
        # ... (no changes)
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"Error creating config directory {CONFIG_DIR}: {e}")

    def load_settings(self):
        # ... (no changes to logic, but uses the new _query_color_from_sysfs_for_zone)
        self.ensure_config_dir_exists()
        config = configparser.ConfigParser()
        loaded_color_from_config = False

        if CONFIG_FILE.exists():
            try:
                config.read(CONFIG_FILE)
                if 'Settings' in config:
                    settings = config['Settings']
                    color_hex_from_config = settings.get('last_color_hex')
                    if color_hex_from_config:
                        temp_color = QColor(color_hex_from_config)
                        if temp_color.isValid():
                            self.current_color = temp_color
                            loaded_color_from_config = True
                            print(f"Loaded color from config: {self.current_color.name()}")
                        else:
                            print(f"Invalid color '{color_hex_from_config}' in config. Using default.")
                    
                    self.target_zone = settings.get('last_target_zone', self.target_zone)
                    if loaded_color_from_config or 'last_target_zone' in settings:
                         print(f"Loaded settings: Zone '{self.target_zone}'")
            except Exception as e:
                print(f"Error processing config settings: {e}. Using defaults.")
                self.current_color = QColor("white")
                loaded_color_from_config = False

        if not loaded_color_from_config:
            print("No valid color in config. Attempting to query sysfs for zone 0 as initial color.")
            # Try to get an initial color from zone 0 (Right) if nothing was loaded
            initial_queried_color = self._query_color_from_sysfs_for_zone("0")
            if initial_queried_color:
                self.current_color = initial_queried_color
            else:
                self.current_color = QColor("white") # Fallback to white
                print("Failed to query initial color from zone 0, defaulting to white.")


    def save_settings(self):
        # ... (no changes)
        self.ensure_config_dir_exists()
        config = configparser.ConfigParser()
        config['Settings'] = {
            'last_color_hex': self.current_color.name(),
            'last_target_zone': self.target_zone
        }
        try:
            with open(CONFIG_FILE, 'w') as configfile:
                config.write(configfile)
            print(f"Settings saved to {CONFIG_FILE}")
        except OSError as e:
            print(f"Error writing config file {CONFIG_FILE}: {e}")
            
    def init_ui(self):
        # ... (no changes to button layout from previous version) ...
        self.setWindowTitle('Omen RGB Control')
        main_layout = QVBoxLayout(self)

        zone_group_layout = QGridLayout()
        zone_label = QLabel("Target Zone:")
        zone_group_layout.addWidget(zone_label, 0, 0, 1, 3)

        self.zone_buttons = {}
        button_definitions = [
            ("Left",   "2",   1, 0, 1, 1), ("Middle", "1",   1, 1, 1, 1), ("Right",  "0",   1, 2, 1, 1),
            ("WSAD",   "3",   2, 0, 1, 1), ("All Zones", "all", 2, 1, 1, 2)
        ]
        for display_text, zone_id, r, c, rs, cs in button_definitions:
            button = QPushButton(display_text)
            button.setCheckable(True)
            button.clicked.connect(lambda checked, current_zid=zone_id: self.select_zone(current_zid))
            self.zone_buttons[zone_id] = button
            zone_group_layout.addWidget(button, r, c, rs, cs)
        main_layout.addLayout(zone_group_layout)
        main_layout.addSpacing(15)

        predefined_colors_layout = QHBoxLayout()
        predefined_colors_label = QLabel("Quick Colors:")
        predefined_colors_layout.addWidget(predefined_colors_label)
        colors = {
            "Red": QColor("red"), "Green": QColor("lime"),
            "Blue": QColor("blue"), "White": QColor("white")
        }
        for name, color_val in colors.items():
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, cv=color_val: self.set_current_color(cv))
            predefined_colors_layout.addWidget(btn)
        predefined_colors_layout.addStretch(1)
        main_layout.addLayout(predefined_colors_layout)

        custom_color_layout = QHBoxLayout()
        color_btn = QPushButton("Custom Color")
        color_btn.clicked.connect(self.show_color_dialog)
        custom_color_layout.addWidget(color_btn)

        self.color_preview = QFrame()
        self.color_preview.setFrameShape(QFrame.Shape.StyledPanel)
        self.color_preview.setMinimumSize(QSize(60, 30))
        self.color_preview.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        custom_color_layout.addWidget(self.color_preview)
        custom_color_layout.addStretch(1)
        main_layout.addLayout(custom_color_layout)
        main_layout.addSpacing(15)

        apply_btn = QPushButton("Apply Settings")
        apply_btn.setFont(QFont(apply_btn.font().family(), 12, QFont.Weight.Bold))
        apply_btn.setMinimumHeight(40)
        apply_btn.clicked.connect(self.apply_settings)
        main_layout.addWidget(apply_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.status_label = QLabel("Ready. Select zone and color.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.status_label)

        self.setLayout(main_layout)
        self.show()


    def update_ui_from_loaded_settings(self):
        # ... (no changes)
        if self.target_zone in self.zone_buttons:
            self.zone_buttons[self.target_zone].setChecked(True)
        else:
            default_zone_id = "all"
            if default_zone_id in self.zone_buttons:
                 self.zone_buttons[default_zone_id].setChecked(True)
                 self.target_zone = default_zone_id
            else:
                 print("Error: Default 'all' zone button not found during UI update.")
        self.update_color_preview()
        self.update_status_label()

    def set_current_color(self, color: QColor):
        # ... (no changes)
        if color.isValid():
            self.current_color = color
            self.update_color_preview()
            self.update_status_label()
        else:
            print(f"Attempted to set an invalid color: {color}")

    def select_zone(self, zone_id: str):
        """Sets the target zone, updates button states, and attempts to query actual zone color."""
        self.target_zone = zone_id
        for zid, button in self.zone_buttons.items():
            button.setChecked(zid == zone_id)
        
        print(f"Target zone set to: '{self.target_zone}'")

        if self.target_zone != "all":
            queried_zone_color = self._query_color_from_sysfs_for_zone(self.target_zone)
            if queried_zone_color:
                # If successfully queried, update current_color to reflect the actual zone color
                self.set_current_color(queried_zone_color)
            else:
                # If query fails, current_color remains as the last globally selected one.
                # The preview will show the color that *will be applied* if the user clicks "Apply".
                print(f"Could not query current color for zone '{self.target_zone}'. "
                      "Color preview shows last selected/default color to be applied.")
        # For "all" zone, self.current_color remains as the globally selected color to be applied.
        
        self.update_status_label() # Update status label after potential color change


    def update_color_preview(self):
        # ... (no changes)
        palette = self.color_preview.palette()
        palette.setColor(QPalette.ColorRole.Window, self.current_color)
        self.color_preview.setPalette(palette)
        self.color_preview.setAutoFillBackground(True)

    def show_color_dialog(self):
        # ... (no changes)
        initial_color_for_dialog = self.current_color if self.current_color.isValid() else QColor("white")
        color = QColorDialog.getColor(initial_color_for_dialog, self, "Choose Custom Color")
        if color.isValid():
            self.set_current_color(color)

    def update_status_label(self):
        # ... (no changes)
        color_name = self.current_color.name().upper() if self.current_color.isValid() else "INVALID"
        zone_display_name = self.target_zone.capitalize() if self.target_zone != "all" else "All"
        if self.target_zone.isdigit():
            zone_display_name = f"Zone {self.target_zone}"
        self.status_label.setText(f"Target: {zone_display_name}, Color: {color_name}")

    def apply_settings(self):
        # ... (no changes)
        if not self.current_color.isValid():
            QMessageBox.warning(self, "Invalid Color", 
                                "Cannot apply an invalid color. Please choose a valid color first.")
            self.status_label.setText("Error: Invalid color selected.")
            return

        color_hex = self.current_color.name()[1:].upper()
        zone_id_str = str(self.target_zone)

        self.status_label.setText(f"Applying {color_hex} to zone '{zone_id_str}'...")
        QApplication.processEvents()

        command = [ "pkexec", HELPER_SCRIPT_PATH, zone_id_str, color_hex ]
        print(f"Executing: {' '.join(shlex.quote(arg) for arg in command)}")

        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=20)
            self.save_settings()
            success_msg = f"Successfully applied {color_hex} to zone '{zone_id_str}'. Settings saved."
            if result.stdout: print(f"Helper script stdout:\n{result.stdout}")
            if result.stderr:
                print(f"Helper script stderr (warnings?):\n{result.stderr}")
                success_msg += " (Helper warnings in console)"
            self.status_label.setText(success_msg)
        except subprocess.CalledProcessError as e:
            error_msg_detail = e.stderr.strip() if e.stderr else e.stdout.strip()
            if not error_msg_detail: error_msg_detail = "Unknown error from helper script or pkexec."
            error_title = "Apply Error"
            full_error_msg = f"Error applying settings (code {e.returncode}).\n"
            if e.returncode == 127:
                 full_error_msg += "pkexec: Authorization failed, policy issue, or helper script not found/executable."
            elif e.returncode == 126:
                 full_error_msg += "pkexec: Authorization cancelled by user."
            else:
                 full_error_msg += f"Helper/pkexec reported: {error_msg_detail}"
            self.status_label.setText("Error applying settings. Check console for details.")
            QMessageBox.warning(self, error_title, full_error_msg)
            print(f"Error during pkexec call. Return code: {e.returncode}\n"
                  f"Stdout from script: {e.stdout}\nStderr from script: {e.stderr}")
        except FileNotFoundError:
             error_msg = "Error: 'pkexec' command not found. Is Polkit (policykit-1) installed and in PATH?"
             self.status_label.setText("Critical Error: pkexec missing.")
             QMessageBox.critical(self, "Startup Error", error_msg)
             print(error_msg)
        except subprocess.TimeoutExpired:
             error_msg = ("Error: Command timed out. \nThis might happen if pkexec is waiting for a password "
                          "and none is provided, or if the helper script is stuck.")
             self.status_label.setText("Timeout Error. Check console for details.")
             QMessageBox.warning(self, "Timeout Error", error_msg)
             print(error_msg)

# --- Main execution ---
if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = OmenRgbGui()
    sys.exit(app.exec())