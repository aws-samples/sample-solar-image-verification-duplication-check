#!/bin/bash
# Save clipboard PNG image to a file (macOS)
# Usage: ./save_clipboard_png.sh <output_path>
osascript -e "set png_data to the clipboard as «class PNGf»
set out_file to open for access POSIX file \"$1\" with write permission
set eof out_file to 0
write png_data to out_file
close access out_file"
