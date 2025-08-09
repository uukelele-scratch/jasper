#!/bin/bash

BLENDER_EXECUTABLE=${BLENDER_PATH:-/usr/bin/blender}
INPUT_DIR="fbx_animations_"
OUTPUT_DIR="animations"


if ! [ -x "$BLENDER_PATH" ]; then
    echo "Error: Blender executable not found at '$BLENDER_PATH'"
    echo "Please update the BLENDER_PATH variable in this script."
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

echo "Starting batch conversion..."
echo "Input folder:  $INPUT_DIR"
echo "Output folder: $OUTPUT_DIR"

for file in "$INPUT_DIR"/*.fbx; do
    [ -e "$file" ] || continue

    filename=$(basename "$file")
    output_file="$OUTPUT_DIR/$filename"

    echo "-----------------------------------------------------"
    echo "Processing: $filename"

    "$BLENDER_PATH" -b --python convert.py -- "$file" "$output_file"

done

echo "-----------------------------------------------------"
echo "Batch conversion complete!"