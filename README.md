# Omen RGB GUI

A simple GUI prototype to control HP Omen 4-zone keyboard RGB lighting on Linux using the hp-wmi kernel module.

## Features

*   Set static color for individual zones (0-3) or all zones at once.
*   Uses Polkit (`pkexec`) for privilege escalation to write to sysfs.

## Dependencies

*   Python 3
*   PyQt6 (`pip install PyQt6`)
*   Working `hp-wmi` kernel module exposing `/sys/devices/platform/hp-wmi/rgb_zones/zoneXX_rgb` files (where XX are hex digits 00-03).
*   Polkit (`polkit` package, usually installed by default on desktop Linux)
*   `pkexec` command (part of Polkit)

## Installation

1.  **Kernel Module:** Make sure the custom `hp-wmi` module is loaded and the sysfs interface exists and is writable by root.
2.  **Helper Script:**
    *   Copy the `helper/omen-rgb-helper.sh` script to a location in the system's PATH accessible by root, typically `/usr/local/bin/omen-rgb-helper.sh`:
        ```bash
        sudo cp helper/omen-rgb-helper.sh /usr/local/bin/omen-rgb-helper.sh
        ```
    *   Make it executable:
        ```bash
        sudo chmod +x /usr/local/bin/omen-rgb-helper.sh
        ```
3.  **Polkit Policy:**
    *   **Verify `policy/com.github.cousteauche.omenrgbgui.policy`**:
        *   Check the `<vendor_url>`.
        *   Ensure the action ID (`com.github.cousteauche.omenrgbgui.applyrgb`) is appropriate.
        *   Verify that the `<annotate key="org.freedesktop.policykit.exec.path">` points to the correct, absolute path of `omen-rgb-helper.sh` (`/usr/local/bin/omen-rgb-helper.sh`).
    *   Copy the `.policy` file to the Polkit actions directory:
        ```bash
        sudo cp policy/com.github.cousteauche.omenrgbgui.policy /usr/share/polkit-1/actions/
        ```
    *   You might need to reload Polkit rules (usually not required, restart might help if needed).
4.  **Python Dependencies:**
    ```bash
    pip install PyQt6
    ```

## Usage

Run the main Python script from the project directory:

```bash
./omen-rgb-gui.py
```
Or:
```bash
python omen-rgb-gui.py
```

Select the target zone(s), choose a color using the "Choose Color" button, and click "Apply Settings". You should be prompted for your administrator password by Polkit.

## TODO

*   Read initial color values from sysfs on startup? (Requires helper script modification or changing sysfs read permissions).
*   More robust error handling and user feedback.
*   Potentially add sliders for R, G, B values.
*   Save/Load color presets.
*   Package properly (e.g., using setuptools, pyproject.toml, AUR package).
*   Add support for brightness and animations once the kernel module supports them.
