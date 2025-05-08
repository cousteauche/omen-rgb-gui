#!/bin/bash

# Simple helper script to set HP Omen RGB zone colors
# Called by pkexec from the GUI.
# Arguments: $1 - Zone ID (0, 1, 2, 3 or "all")
#            $2 - Color in hex format (e.g., FFFFFF)

ZONE_ID=$1
COLOR_HEX=$2
SYSFS_BASE="/sys/devices/platform/hp-wmi/rgb_zones"

# --- Basic Validation ---
if [[ -z "$ZONE_ID" || -z "$COLOR_HEX" ]]; then
  echo "Usage: $0 <zone_id|all> <RRGGBB_HEX>" >&2
  exit 1
fi

# Check color format (6 hex chars)
if ! [[ "$COLOR_HEX" =~ ^[0-9A-Fa-f]{6}$ ]]; then
  echo "Error: Invalid color format. Use RRGGBB hex (e.g., FF0000)." >&2
  exit 1
fi

# --- Write Function ---
write_color() {
  local zone_num=$1
  local zone_hex
  printf -v zone_hex "%02X" "$zone_num" # Format zone number as two hex digits
  local sysfs_file="${SYSFS_BASE}/zone${zone_hex}_rgb"

  if [ ! -w "$sysfs_file" ]; then
     if [ ! -e "$sysfs_file" ]; then
        echo "Error: Sysfs file not found: $sysfs_file" >&2
        return 1
     fi
     echo "Warning: Sysfs file might not be writable: $sysfs_file (Continuing as root...)" >&2
     # Still attempt to write, pkexec should grant permission
  fi

  # Use process substitution to avoid issues with echo -n portability if any
  # Though echo -n is quite standard nowadays
  # exec > "$sysfs_file" <<< "$COLOR_HEX"
  # Or simply:
  echo -n "$COLOR_HEX" > "$sysfs_file"


  if [ $? -ne 0 ]; then
    echo "Error: Failed to write to $sysfs_file" >&2
    return 1
  fi
  # echo "Successfully set zone $zone_hex to $COLOR_HEX" # Optional success log
  return 0
}

# --- Zone Logic ---
RC=0
if [[ "$ZONE_ID" == "all" ]]; then
  for i in {0..3}; do
    write_color "$i" || RC=1 # Set RC=1 if any write fails
  done
elif [[ "$ZONE_ID" =~ ^[0-3]$ ]]; then
  write_color "$ZONE_ID" || RC=1
else
  echo "Error: Invalid zone ID. Use 0, 1, 2, 3, or 'all'." >&2
  RC=1
fi

exit $RC
