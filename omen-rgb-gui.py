#!/usr/bin/env python

import sys
import subprocess
import shlex
import configparser
from pathlib import Path
import os # For os.makedirs, though Path.mkdir is used in ensure_config_dir_exists
import re # For parsing sysfs output

from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QColorDialog, QFrame, QSizePolicy, QMessageBox, QGridLayout
)
from PyQt6.QtGui import QColor, QPalette, QFont
from PyQt6.QtCore import Qt, QSize

# Path to the helper script (this path is used by pkexec)
HELPER_SCRIPT_PATH = "/usr/local/bin/omen-rgb-helper.sh"
# Polkit action ID (must match the id in the .policy file)
# Although we call pkexec with HELPER_SCRIPT_PATH directly,
# the .policy file uses this action ID to grant permission for that script.
POLKIT_ACTION = "com.github.cousteauche.omenrgbgui.applyrgb" # As per your .policy file

# Configuration file path
CONFIG_DIR = Path.home() / ".config" / "omenrgbgui"
CONFIG_FILE = CONFIG_DIR / "settings.ini"

# Sysfs path for initial color query (zone 0 is often a good default to check)
# This path might need adjustment based on the specific HP Omen model / kernel module version
SYSFS_ZONE0_RGB_PATH = "/sys/devices/platform/hp-wmi/rgb_zones/zone00_rgb" # For "Right" zone (0)

class OmenRgbGui(QWidget):
    def __init__(self):
        super().__init__()
        self.current_color = QColor("white") # Default color if nothing is loaded/queried
        self.target_zone = "all"             # Default target zone

        self.load_settings() # Load settings before initializing UI components
        self.init_ui()
        self.update_ui_from_loaded_settings() # Apply loaded/default settings to UI elements

    def ensure_config_dir_exists(self):
        """Ensures the configuration directory exists."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"Error creating config directory {CONFIG_DIR}: {e}")
            # This is non-critical; the app can still run without saving/loading settings.

    def load_settings(self):
        """Loads the last used color and target zone from the configuration file."""
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
                        # QColor constructor expects #RRGGBB, #RGB, or a valid color name
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
            except configparser.Error as e:
                print(f"Error reading config file {CONFIG_FILE}: {e}")
            except Exception as e: # Catch other potential errors, e.g., from QColor
                print(f"Error processing config settings: {e}. Using defaults.")
                self.current_color = QColor("white") # Reset to a known good default
                loaded_color_from_config = False

        if not loaded_color_from_config:
            print("No valid color in config or config not found. Attempting to query sysfs for initial color.")
            self.query_initial_color_from_sysfs()

    def query_initial_color_from_sysfs(self):
        """
        Tries to read the initial color for a default zone (e.g., zone 0) from sysfs.
        This is a fallback if no color is loaded from the config file.
        Note: Reading from sysfs might require user permissions for the GUI process,
              or the sysfs files might not be readable by default for non-root users.
        """
        try:
            with open(SYSFS_ZONE0_RGB_PATH, 'r') as f:
                content = f.read().strip() # Example content: 'RGB:aa55ff (R:170 G:85 B:255)'
                
                # Use regex to find a 6-digit hex string within the content
                match = re.search(r'([0-9a-fA-F]{6})', content)
                if match:
                    hex_color = match.group(1)
                    parsed_qcolor = QColor(f"#{hex_color}") # Prepend '#' for QColor
                    if parsed_qcolor.isValid():
                        self.current_color = parsed_qcolor
                        print(f"Queried initial color from sysfs ({SYSFS_ZONE0_RGB_PATH}): {self.current_color.name()}")
                    else:
                        print(f"Invalid hex color '#{hex_color}' parsed from sysfs content '{content}'. Using default white.")
                        self.current_color = QColor("white")
                else:
                    print(f"Could not parse 6-digit hex color from sysfs content: '{content}' in {SYSFS_ZONE0_RGB_PATH}. Using default white.")
                    self.current_color = QColor("white")
        except FileNotFoundError:
            print(f"Sysfs file for default zone not found: {SYSFS_ZONE0_RGB_PATH}. Cannot query initial color. Using default white.")
            self.current_color = QColor("white")
        except PermissionError:
            print(f"Permission denied reading {SYSFS_ZONE0_RGB_PATH}. Cannot query initial color. Using default white.")
            self.current_color = QColor("white")
        except Exception as e:
            print(f"Error reading initial color from sysfs: {e}. Using default white.")
            self.current_color = QColor("white")

    def save_settings(self):
        """Saves the current color and target zone to the configuration file."""
        self.ensure_config_dir_exists()
        config = configparser.ConfigParser()
        config['Settings'] = {
            'last_color_hex': self.current_color.name(), # Stores as #RRGGBB
            'last_target_zone': self.target_zone
        }
        try:
            with open(CONFIG_FILE, 'w') as configfile:
                config.write(configfile)
            print(f"Settings saved to {CONFIG_FILE}")
        except OSError as e:
            print(f"Error writing config file {CONFIG_FILE}: {e}")

    def init_ui(self):
        self.setWindowTitle('Omen RGB Control') # English window title
        main_layout = QVBoxLayout(self)

        # --- Zone Selection ---
        zone_group_layout = QGridLayout()
        zone_label = QLabel("Target Zone:")
        zone_group_layout.addWidget(zone_label, 0, 0, 1, 3) # Span label across 3 columns

        self.zone_buttons = {}
        
        # Define buttons: (Display Text, Zone ID, Grid Row, Grid Col, Row Span, Col Span)
        button_definitions = [
            # Row 1
            ("Left",   "2",   1, 0, 1, 1), # (zone 2)
            ("Middle", "1",   1, 1, 1, 1), # (zone 1)
            ("Right",  "0",   1, 2, 1, 1), # (zone 0)
            # Row 2
            ("WSAD",      "3",   2, 0, 1, 1), # (zone 3)
            ("All Zones", "all", 2, 1, 1, 2)  # Spans 2 columns (middle and right)
        ]
        
        for display_text, zone_id, r, c, rs, cs in button_definitions:
            button = QPushButton(display_text)
            button.setCheckable(True)
            # Lambda captures current_zid for each button correctly
            button.clicked.connect(lambda checked, current_zid=zone_id: self.select_zone(current_zid))
            self.zone_buttons[zone_id] = button
            zone_group_layout.addWidget(button, r, c, rs, cs)

        main_layout.addLayout(zone_group_layout)
        main_layout.addSpacing(15) # More spacing

        # --- Predefined Color Buttons ---
        predefined_colors_layout = QHBoxLayout()
        predefined_colors_label = QLabel("Quick Colors:")
        predefined_colors_layout.addWidget(predefined_colors_label)
        
        # Color names and their QColor values
        colors = {
            "Red": QColor("red"), "Green": QColor("lime"), # Using "lime" for a brighter green
            "Blue": QColor("blue"), "White": QColor("white")
        }
        for name, color_val in colors.items():
            btn = QPushButton(name)
            # Lambda captures color_val (cv) for each button
            btn.clicked.connect(lambda checked, cv=color_val: self.set_current_color(cv))
            predefined_colors_layout.addWidget(btn)
        predefined_colors_layout.addStretch(1) # Push buttons to the left
        main_layout.addLayout(predefined_colors_layout)

        # --- Custom Color Selection ---
        custom_color_layout = QHBoxLayout()
        color_btn = QPushButton("Custom Color") # Button to open color dialog
        color_btn.clicked.connect(self.show_color_dialog)
        custom_color_layout.addWidget(color_btn)

        self.color_preview = QFrame() # Frame to show selected color
        self.color_preview.setFrameShape(QFrame.Shape.StyledPanel)
        self.color_preview.setMinimumSize(QSize(60, 30)) # Make preview a bit larger
        self.color_preview.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        custom_color_layout.addWidget(self.color_preview)
        custom_color_layout.addStretch(1) # Push to the left
        main_layout.addLayout(custom_color_layout)
        main_layout.addSpacing(15)

        # --- Apply Button ---
        apply_btn = QPushButton("Apply Settings")
        apply_btn.setFont(QFont(apply_btn.font().family(), 12, QFont.Weight.Bold)) # Make it prominent
        apply_btn.setMinimumHeight(40)
        apply_btn.clicked.connect(self.apply_settings)
        main_layout.addWidget(apply_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # --- Status Label ---
        self.status_label = QLabel("Ready. Select zone and color.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.status_label)

        self.setLayout(main_layout)
        self.show()

    def update_ui_from_loaded_settings(self):
        """Applies loaded or default settings to UI elements after init_ui."""
        if self.target_zone in self.zone_buttons:
            self.zone_buttons[self.target_zone].setChecked(True)
        else: # Fallback if loaded zone_id is somehow invalid
            default_zone_id = "all"
            if default_zone_id in self.zone_buttons: # Ensure 'all' button exists
                 self.zone_buttons[default_zone_id].setChecked(True)
                 self.target_zone = default_zone_id
            else: # Should not happen if 'all' is always in button_definitions
                 print("Error: Default 'all' zone button not found during UI update.")
        
        self.update_color_preview()
        self.update_status_label()

    def set_current_color(self, color: QColor):
        """Sets the current color and updates the preview."""
        if color.isValid():
            self.current_color = color
            self.update_color_preview()
            self.update_status_label()
        else:
            print(f"Attempted to set an invalid color: {color}")

    def select_zone(self, zone_id: str):
        """Sets the target zone and updates button states."""
        self.target_zone = zone_id
        for zid, button in self.zone_buttons.items():
            button.setChecked(zid == zone_id)
        self.update_status_label()
        print(f"Target zone set to: {self.target_zone}")

    def update_color_preview(self):
        """Updates the color_preview QFrame with the current_color."""
        palette = self.color_preview.palette()
        palette.setColor(QPalette.ColorRole.Window, self.current_color)
        self.color_preview.setPalette(palette)
        self.color_preview.setAutoFillBackground(True)

    def show_color_dialog(self):
        """Shows the QColorDialog to pick a custom color."""
        # Ensure a valid color is passed as the initial color to the dialog
        initial_color_for_dialog = self.current_color if self.current_color.isValid() else QColor("white")
        color = QColorDialog.getColor(initial_color_for_dialog, self, "Choose Custom Color")
        if color.isValid():
            self.set_current_color(color)

    def update_status_label(self):
        """Updates the status label with the current zone and color."""
        color_name = self.current_color.name().upper() if self.current_color.isValid() else "INVALID"
        # Capitalize zone ID, or use "All" for "all"
        zone_display_name = self.target_zone.capitalize() if self.target_zone != "all" else "All"
        if self.target_zone.isdigit(): # If it's a numerical zone, prefix with "Zone"
            zone_display_name = f"Zone {self.target_zone}"
        
        self.status_label.setText(f"Target: {zone_display_name}, Color: {color_name}")


    def apply_settings(self):
        """Applies the selected color to the selected zone(s) using the helper script via pkexec."""
        if not self.current_color.isValid():
            QMessageBox.warning(self, "Invalid Color", 
                                "Cannot apply an invalid color. Please choose a valid color first.")
            self.status_label.setText("Error: Invalid color selected.")
            return

        color_hex = self.current_color.name()[1:].upper() # Remove '#' and convert to uppercase
        zone_id_str = str(self.target_zone)

        # Update status label before running the command
        self.status_label.setText(f"Applying {color_hex} to zone '{zone_id_str}'...")
        QApplication.processEvents() # Refresh the GUI to show the "Applying..." message

        command = [
            "pkexec",
            HELPER_SCRIPT_PATH, # Direct path to the helper script
            zone_id_str,
            color_hex
        ]
        print(f"Executing: {' '.join(shlex.quote(arg) for arg in command)}")

        try:
            # Run the command, capture output, check for errors, and set a timeout
            result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=20)
            
            self.save_settings() # Save settings on successful application
            
            success_msg = f"Successfully applied {color_hex} to zone '{zone_id_str}'. Settings saved."
            
            if result.stdout: # Log stdout from helper if any
                print(f"Helper script stdout:\n{result.stdout}")
            if result.stderr: # Log stderr from helper (could be warnings even on success)
                print(f"Helper script stderr (warnings?):\n{result.stderr}")
                success_msg += " (Helper warnings in console)"

            self.status_label.setText(success_msg)

        except subprocess.CalledProcessError as e:
            # This catches errors where the helper script itself returns a non-zero exit code,
            # or pkexec fails for reasons other than cancellation/not found.
            error_msg_detail = e.stderr.strip() if e.stderr else e.stdout.strip()
            if not error_msg_detail: error_msg_detail = "Unknown error from helper script or pkexec."
            
            error_title = "Apply Error"
            full_error_msg = f"Error applying settings (code {e.returncode}).\n"
            
            if e.returncode == 127: # pkexec: command not found in policy, or policy issue, or helper script issue
                 full_error_msg += "pkexec: Authorization failed, policy issue, or helper script not found/executable."
            elif e.returncode == 126: # pkexec: user cancelled authorization
                 full_error_msg += "pkexec: Authorization cancelled by user."
            else: # Error from the helper script itself or other pkexec issue
                 full_error_msg += f"Helper/pkexec reported: {error_msg_detail}"
            
            self.status_label.setText("Error applying settings. Check console for details.")
            QMessageBox.warning(self, error_title, full_error_msg)
            # Log detailed error info to console for debugging
            print(f"Error during pkexec call. Return code: {e.returncode}\n"
                  f"Stdout from script: {e.stdout}\nStderr from script: {e.stderr}")

        except FileNotFoundError:
             # This means 'pkexec' itself was not found in the system's PATH
             error_msg = "Error: 'pkexec' command not found. Is Polkit (policykit-1) installed and in PATH?"
             self.status_label.setText("Critical Error: pkexec missing.")
             QMessageBox.critical(self, "Startup Error", error_msg)
             print(error_msg)
        except subprocess.TimeoutExpired:
             # The command took too long (e.g., pkexec waiting for password, or helper script stuck)
             error_msg = "Error: Command timed out. \n" \
                         "This might happen if pkexec is waiting for a password and none is provided, " \
                         "or if the helper script is stuck."
             self.status_label.setText("Timeout Error. Check console for details.")
             QMessageBox.warning(self, "Timeout Error", error_msg)
             print(error_msg)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Optional: Apply a style for a more modern look, depending on the desktop environment
    # app.setStyle("Fusion") 
    ex = OmenRgbGui()
    sys.exit(app.exec())