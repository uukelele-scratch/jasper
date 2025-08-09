# convert.py (Modern GLB Exporter for Blender 4.x)
# This script converts FBX files to GLB, the format best supported by Panda3D.

import bpy
import sys

def convert_file(input_path, output_path):
    if bpy.ops.object.select_all.poll():
        bpy.ops.object.select_all(action='SELECT')
    if bpy.ops.object.delete.poll():
        bpy.ops.object.delete(use_global=False)

    print(f"Importing FBX: {input_path}")
    bpy.ops.import_scene.fbx(filepath=input_path)

    print(f"Exporting GLB to: {output_path}")
    bpy.ops.export_scene.gltf(
        filepath=output_path,
        export_format='GLB',
        export_animations=True,
        export_skins=True,
        export_yup=True,
    )

if __name__ == "__main__":
    argv = sys.argv
    try:
        args = argv[argv.index("--") + 1:]
    except ValueError:
        args = []

    if len(args) < 2:
        print("Error: Missing input and output file paths.")
        bpy.ops.wm.quit_blender()
    else:
        input_file = args[0]
        output_file = args[1].rsplit('.', 1)[0] + '.glb'
        convert_file(input_file, output_file)
        print("Conversion successful.")