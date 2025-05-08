#!/usr/bin/env python

import sys
import subprocess
import shlex
import configparser
from pathlib import Path
import os
import re # Added for parsing sysfs output

from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QColorDialog, QFrame, QSizePolicy, QMessageBox, QGridLayout
)
from PyQt6.QtGui import QColor, QPalette, QFont
from PyQt6.QtCore import Qt, QSize

# Path to the helper script (referenced by Polkit policy)
HELPER_SCRIPT_PATH = "/usr/local/bin/omen-rgb-helper.sh"
# Polkit action (must match the .policy file's action id)
POLKIT_ACTION = "com.github.cousteauche.omenrgbgui.applyrgb" # As per your current script

# Configuration file path
CONFIG_DIR = Path.home() / ".config" / "omenrgbgui"
CONFIG_FILE = CONFIG_DIR / "settings.ini"

# Sysfs path for initial color query (zone 0)
SYSFS_ZONE0_RGB_PATH = "/sys/devices/platform/hp-wmi/rgb_zones/zone00_rgb"

class OmenRgbGui(QWidget):
    def __init__(self):
        super().__init__()
        self.current_color = QColor("white") # Default color
        self.target_zone = "all" # Default target

        self.load_settings() # Load settings before UI init
        self.init_ui()
        self.update_ui_from_loaded_settings() # Apply loaded settings to UI elements

    def ensure_config_dir_exists(self):
        """Ensures the configuration directory exists."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"Error creating config directory {CONFIG_DIR}: {e}")

    def load_settings(self):
        """Loads color and zone from the configuration file."""
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
                        # QColor constructor expects #RRGGBB, #RGB, or color name
                        temp_color = QColor(color_hex_from_config)
                        if temp_color.isValid():
                            self.current_color = temp_color
                            loaded_color_from_config = True
                            print(f"Loaded color from config: {self.current_color.name()}")
                        else:
                            print(f"Invalid color '{color_hex_from_config}' in config. Using default.")
                    
                    self.target_zone = settings.get('last_target_zone', self.target_zone)
                    if loaded_color_from_config or 'last_target_zone' in settings: # Print if anything was loaded
                         print(f"Loaded settings: Zone {self.target_zone}")
            except configparser.Error as e:
                print(f"Error reading config file {CONFIG_FILE}: {e}")
            except Exception as e:
                print(f"Error processing config settings: {e}. Using defaults.")
                self.current_color = QColor("white")
                loaded_color_from_config = False

        if not loaded_color_from_config:
            print("No valid color in config or config not found, attempting to query sysfs.")
            self.query_initial_color_from_sysfs()

    def query_initial_color_from_sysfs(self):
        """Tries to read the initial color for zone 0 from sysfs."""
        try:
            with open(SYSFS_ZONE0_RGB_PATH, 'r') as f:
                content = f.read().strip() # e.g., 'RGB:aa55ff (R:170 G:85 B:255)'
                
                # Use regex to find a 6-digit hex string
                match = re.search(r'([0-9a-fA-F]{6})', content)
                if match:
                    hex_color = match.group(1)
                    parsed_qcolor = QColor(f"#{hex_color}") # Prepend #
                    if parsed_qcolor.isValid():
                        self.current_color = parsed_qcolor
                        print(f"Queried initial color from sysfs ({SYSFS_ZONE0_RGB_PATH}): {self.current_color.name()}")
                    else:
                        # This case should be rare if regex is correct and QColor handles hex well
                        print(f"Invalid hex color '#{hex_color}' parsed from sysfs content '{content}'. Using default white.")
                        self.current_color = QColor("white")
                else:
                    print(f"Could not parse 6-digit hex color from sysfs content: '{content}' in {SYSFS_ZONE0_RGB_PATH}. Using default white.")
                    self.current_color = QColor("white")
        except FileNotFoundError:
            print(f"Sysfs file for zone 0 not found: {SYSFS_ZONE0_RGB_PATH} (Cannot query initial color). Using default white.")
            self.current_color = QColor("white")
        except PermissionError:
            print(f"Permission denied reading {SYSFS_ZONE0_RGB_PATH} (Cannot query initial color). Using default white.")
            self.current_color = QColor("white")
        except Exception as e:
            print(f"Error reading initial color from sysfs: {e}. Using default white.")
            self.current_color = QColor("white")

    def save_settings(self):
        """Saves the current color and zone to the configuration file."""
        self.ensure_config_dir_exists()
        config = configparser.ConfigParser()
        config['Settings'] = {
            'last_color_hex': self.current_color.name(), # #RRGGBB
            'last_target_zone': self.target_zone
        }
        try:
            with open(CONFIG_FILE, 'w') as configfile:
                config.write(configfile)
            print(f"Settings saved to {CONFIG_FILE}")
        except OSError as e:
            print(f"Error writing config file {CONFIG_FILE}: {e}")


    def init_ui(self):
        self.setWindowTitle('Omen RGB GUI')
        main_layout = QVBoxLayout(self)

        zone_group_layout = QGridLayout()
        zone_label = QLabel("Target Zone:")
        zone_group_layout.addWidget(zone_label, 0, 0, 1, 3)

        self.zone_buttons = {}
        zone_targets = ["Zone 0", "Zone 1", "Zone 2", "Zone 3", "All Zones"]
        zone_ids = ["0", "1", "2", "3", "all"]
        positions = [(1, 0), (1, 1), (1, 2), (2, 0), (2, 1)]

        for i, text in enumerate(zone_targets):
            button = QPushButton(text)
            button.setCheckable(True)
            button.clicked.connect(lambda checked, zid=zone_ids[i]: self.select_zone(zid)) # Pass 'checked' argument
            self.zone_buttons[zone_ids[i]] = button
            row, col = positions[i]
            zone_group_layout.addWidget(button, row, col)
        
        main_layout.addLayout(zone_group_layout)
        main_layout.addSpacing(10)

        predefined_colors_layout = QHBoxLayout()
        predefined_colors_label = QLabel("Quick Colors:")
        predefined_colors_layout.addWidget(predefined_colors_label)
        
        colors = {
            "Red": QColor("red"), "Green": QColor("lime"), 
            "Blue": QColor("blue"), "White": QColor("white")
        }
        for name, color_val in colors.items():
            btn = QPushButton(name)
            # Corrected lambda: 'checked' captures the bool from clicked(), 'cv' captures color_val
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
        main_layout.addSpacing(10)

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
        if self.target_zone in self.zone_buttons:
            self.zone_buttons[self.target_zone].setChecked(True)
        else:
            self.zone_buttons["all"].setChecked(True)
            self.target_zone = "all"
        
        self.update_color_preview()
        self.update_status_label()

    def set_current_color(self, color: QColor):
        # This method now correctly receives a QColor object
        if color.isValid():
            self.current_color = color
            self.update_color_preview()
            self.update_status_label()
        else:
            print(f"Attempted to set an invalid color: {color}")


    def select_zone(self, zone_id): # Removed 'checked' from here, it's handled by lambda
        self.target_zone = zone_id
        for zid, button in self.zone_buttons.items():
            button.setChecked(zid == zone_id)
        self.update_status_label()
        print(f"Target zone set to: {self.target_zone}")


    def update_color_preview(self):
        palette = self.color_preview.palette()
        palette.setColor(QPalette.ColorRole.Window, self.current_color)
        self.color_preview.setPalette(palette)
        self.color_preview.setAutoFillBackground(True)

    def show_color_dialog(self):
        # Make sure self.current_color is valid before passing to getColor
        initial_color = self.current_color if self.current_color.isValid() else QColor("white")
        color = QColorDialog.getColor(initial_color, self, "Choose Custom Color")
        if color.isValid():
            self.set_current_color(color)

    def update_status_label(self):
        color_name = self.current_color.name().upper() if self.current_color.isValid() else "INVALID"
        self.status_label.setText(f"Zone: {self.target_zone.capitalize()}, Color: {color_name}")

    def apply_settings(self):
        if not self.current_color.isValid():
            QMessageBox.warning(self, "Invalid Color", "Cannot apply an invalid color. Please choose a valid color.")
            self.status_label.setText("Error: Invalid color selected.")
            return

        color_hex = self.current_color.name()[1:].upper()
        zone_id_str = str(self.target_zone)

        self.status_label.setText(f"Applying {color_hex} to {zone_id_str}...")
        QApplication.processEvents()

        # In OmenRgbGui class, apply_settings method:
        command = [
            "pkexec",
            HELPER_SCRIPT_PATH, # This is "/usr/local/bin/omen-rgb-helper.sh"
            zone_id_str,
            color_hex
        ]
        print(f"Executing: {' '.join(shlex.quote(arg) for arg in command)}")

        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=20)
            
            success_msg = f"Successfully applied {color_hex} to zone {zone_id_str}."
            if result.stdout:
                print(f"Helper script stdout:\n{result.stdout}")
            if result.stderr:
                print(f"Helper script stderr (warnings?):\n{result.stderr}")
                success_msg += " (with warnings from helper)"

            self.status_label.setText(success_msg)
            self.save_settings()

        except subprocess.CalledProcessError as e:
            error_msg_detail = e.stderr.strip() if e.stderr else e.stdout.strip()
            if not error_msg_detail: error_msg_detail = "Unknown error from helper script or pkexec."
            
            error_msg = f"Error (code {e.returncode}).\n"
            if e.returncode == 127: 
                 error_msg += "pkexec: Authorization failed, policy issue, or helper not found by policy."
            elif e.returncode == 126: 
                 error_msg += "pkexec: Authorization cancelled by user."
            else: 
                 error_msg += f"Helper/pkexec: {error_msg_detail}"
            
            self.status_label.setText("Error applying settings.")
            QMessageBox.warning(self, "Apply Error", error_msg)
            print(f"Error executing: {error_msg_detail}\nStdout: {e.stdout}\nStderr: {e.stderr}")

        except FileNotFoundError:
             error_msg = f"Error: pkexec command not found. Is Polkit installed and in PATH?"
             self.status_label.setText("Critical Error: pkexec missing.")
             QMessageBox.critical(self, "Startup Error", error_msg)
             print(error_msg)
        except subprocess.TimeoutExpired:
             error_msg = "Error: Command timed out (pkexec waiting for password, or helper script stuck)."
             self.status_label.setText("Timeout Error.")
             QMessageBox.warning(self, "Timeout Error", error_msg)
             print(error_msg)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = OmenRgbGui()
    sys.exit(app.exec())
