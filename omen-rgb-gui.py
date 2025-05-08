#!/usr/bin/env python

import sys
import subprocess
import shlex
from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QColorDialog, QFrame, QSizePolicy, QMessageBox, QGridLayout # Dodano QGridLayout
)
from PyQt6.QtGui import QColor, QPalette, QFont
from PyQt6.QtCore import Qt, QSize

# Path to the helper script (must match the .policy file)
HELPER_SCRIPT_PATH = "/usr/local/bin/omen-rgb-helper.sh"
# Polkit action (must match the .policy file)
POLKIT_ACTION = "com.github.cousteauche.omenrgbgui.applyrgb"

class OmenRgbGui(QWidget):
    def __init__(self):
        super().__init__()
        self.current_color = QColor("white") # Default color
        self.target_zone = "all" # Default target

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Omen RGB GUI (Prototype)')

        main_layout = QVBoxLayout(self)

        # --- Zone Selection (Grid Layout) ---
        zone_group_layout = QGridLayout()
        zone_label = QLabel("Target Zone:")
        zone_group_layout.addWidget(zone_label, 0, 0, 1, 3) # Span label across 3 columns

        self.zone_buttons = {}
        zone_targets = ["Zone 0", "Zone 1", "Zone 2", "Zone 3", "All Zones"]
        zone_ids = ["0", "1", "2", "3", "all"] # IDs passed to helper
        positions = [(1, 0), (1, 1), (1, 2), (2, 0), (2, 1)] # Pozycje w siatce

        for i, text in enumerate(zone_targets):
            button = QPushButton(text)
            button.setCheckable(True)
            button.clicked.connect(lambda checked, zid=zone_ids[i]: self.select_zone(zid))
            self.zone_buttons[zone_ids[i]] = button
            row, col = positions[i]
            zone_group_layout.addWidget(button, row, col)

        # Add stretch to fill remaining space if needed
        # zone_group_layout.setColumnStretch(2, 1) # Stretch last column if layout looks cramped

        self.zone_buttons["all"].setChecked(True) # Default selection
        main_layout.addLayout(zone_group_layout)


        # --- Color Selection ---
        color_layout = QHBoxLayout()
        color_btn = QPushButton("Choose Color")
        color_btn.clicked.connect(self.show_color_dialog)
        color_layout.addWidget(color_btn)

        self.color_preview = QFrame()
        self.color_preview.setFrameShape(QFrame.Shape.StyledPanel)
        self.color_preview.setMinimumSize(QSize(50, 30))
        self.color_preview.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.update_color_preview() # Set initial color
        color_layout.addWidget(self.color_preview)
        color_layout.addStretch(1)

        main_layout.addLayout(color_layout)

        # --- Apply Button ---
        apply_btn = QPushButton("Apply Settings")
        apply_btn.setFont(QFont(apply_btn.font().family(), 12))
        apply_btn.clicked.connect(self.apply_settings)
        main_layout.addWidget(apply_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # --- Status ---
        self.status_label = QLabel("Ready.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.status_label)

        self.setLayout(main_layout)
        self.show()

    def select_zone(self, zone_id):
        self.target_zone = zone_id
        for zid, button in self.zone_buttons.items():
            button.setChecked(zid == zone_id)
        print(f"Target zone set to: {self.target_zone}")

    def update_color_preview(self):
        palette = self.color_preview.palette()
        palette.setColor(QPalette.ColorRole.Window, self.current_color)
        self.color_preview.setPalette(palette)
        self.color_preview.setAutoFillBackground(True)

    def show_color_dialog(self):
        color = QColorDialog.getColor(self.current_color, self)
        if color.isValid():
            self.current_color = color
            self.update_color_preview()
            print(f"Color chosen: {self.current_color.name().upper()}")

    def apply_settings(self):
        color_hex = self.current_color.name()[1:].upper() # Remove '#' and uppercase
        zone_id_str = str(self.target_zone)

        self.status_label.setText(f"Applying {color_hex} to zone {zone_id_str}...")
        QApplication.processEvents() # Refresh GUI

        # Use pkexec to run the helper script as root
        command = [
            "pkexec",
            HELPER_SCRIPT_PATH,
            zone_id_str,
            color_hex
        ]

        print(f"Executing: {' '.join(shlex.quote(arg) for arg in command)}")

        try:
            # Use timeout to prevent hanging if pkexec waits indefinitely
            result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=15)
            print(f"Helper script stdout:\n{result.stdout}")
            print(f"Helper script stderr:\n{result.stderr}")
            self.status_label.setText(f"Successfully applied {color_hex} to zone {zone_id_str}.")
        except subprocess.CalledProcessError as e:
            print(f"Error executing helper script:")
            print(f"Return code: {e.returncode}")
            print(f"Stderr: {e.stderr}")
            print(f"Stdout: {e.stdout}")
            error_msg = f"Error applying settings (code {e.returncode}).\n"
            if e.returncode == 127: # pkexec error (e.g., policy, helper not found)
                 error_msg += "Authorization failed or helper script not found/executable."
            elif e.returncode == 126: # pkexec - user cancelled
                 error_msg += "Authorization cancelled by user."
            else: # Error from the helper script itself
                 error_msg += e.stderr.strip() if e.stderr else "Unknown error from helper script."
            self.status_label.setText(f"Error.")
            QMessageBox.warning(self, "Error", error_msg)
        except FileNotFoundError:
             error_msg = f"Error: pkexec command not found. Is Polkit installed and in PATH?"
             print(error_msg)
             self.status_label.setText(f"Error.")
             QMessageBox.critical(self, "Error", error_msg)
        except subprocess.TimeoutExpired:
             error_msg = "Error: Command timed out (maybe waiting for password?)."
             print(error_msg)
             self.status_label.setText(f"Error.")
             QMessageBox.warning(self, "Error", error_msg)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = OmenRgbGui()
    sys.exit(app.exec())
