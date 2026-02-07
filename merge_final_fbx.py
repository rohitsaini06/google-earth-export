import bpy
import os
import sys
import time

# ---------------- CONFIG ----------------
INPUT_DIR = sys.argv[-2]  # Directory containing batch FBX files
OUTPUT_FBX = sys.argv[-1]  # Final merged output
BAR_WIDTH = 40

# ---------------- HELPERS ----------------
def format_time(seconds):
    if seconds <= 0:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def print_progress(current, total, elapsed, last_file):
    progress = current / total
    filled = int(BAR_WIDTH * progress)
    bar = "█" * filled + "─" * (BAR_WIDTH - filled)

    eta = (elapsed / current * (total - current)) if current > 0 else 0

    line = (
        f"[{bar}] "
        f"{current}/{total} | "
        f"ETA {format_time(eta)} | "
        f"Last: {last_file}"
    )

    print("\r" + line[:120], end="", flush=True)

# ---------------- START ----------------
start_time = time.time()
print("=" * 60)
print("Final FBX Merge Started")
print("=" * 60)
print(f"Input directory: {INPUT_DIR}")
print(f"Output file: {OUTPUT_FBX}")
print()

# Reset scene
bpy.ops.wm.read_factory_settings(use_empty=True)

# Collect batch FBX files
fbx_files = sorted(f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".fbx"))
total = len(fbx_files)

if total == 0:
    print("ERROR: No FBX files found in input directory")
    sys.exit(1)

print(f"Found {total} batch FBX files to merge")
print()

# ---------------- IMPORT WITH PROGRESS ----------------
print("Importing batch FBX files...")
imported_count = 0
failed_count = 0

for idx, file in enumerate(fbx_files, 1):
    path = os.path.join(INPUT_DIR, file)

    try:
        bpy.ops.import_scene.fbx(filepath=path)
        imported_count += 1
    except Exception as e:
        print(f"\nERROR importing {file}: {e}")
        failed_count += 1

    elapsed = time.time() - start_time
    print_progress(idx, total, elapsed, file)

print()  # newline after progress bar
print(f"Successfully imported: {imported_count}/{total}")
if failed_count > 0:
    print(f"Failed imports: {failed_count}")
print()

# ---------------- COUNT OBJECTS ----------------
mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
total_meshes = len(mesh_objects)

if total_meshes == 0:
    print("ERROR: No mesh objects found after import")
    sys.exit(1)

print(f"Total mesh objects: {total_meshes}")
print()

# ---------------- MATERIAL OPTIMIZATION ----------------
print("Optimizing materials...")

# Remove duplicate materials
material_map = {}
removed_materials = 0

for mat in bpy.data.materials:
    if mat.name not in material_map:
        material_map[mat.name] = mat
    else:
        # Replace references to duplicate materials
        for obj in bpy.data.objects:
            if obj.type == 'MESH':
                for slot in obj.material_slots:
                    if slot.material == mat:
                        slot.material = material_map[mat.name]
        bpy.data.materials.remove(mat)
        removed_materials += 1

print(f"Removed {removed_materials} duplicate materials")
print(f"Unique materials: {len(material_map)}")
print()

# ---------------- SELECT & JOIN ----------------
print(f"Joining {total_meshes} meshes into single object...")

bpy.ops.object.select_all(action='DESELECT')

for obj in mesh_objects:
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

# Join all meshes
join_start = time.time()
bpy.ops.object.join()
join_time = time.time() - join_start

print(f"Join completed in {format_time(join_time)}")

# Get final merged object
merged_obj = bpy.context.view_layer.objects.active
if merged_obj:
    vertex_count = len(merged_obj.data.vertices)
    face_count = len(merged_obj.data.polygons)
    print(f"Final mesh stats:")
    print(f"  Vertices: {vertex_count:,}")
    print(f"  Faces: {face_count:,}")
print()

# ---------------- EXPORT ----------------
print("Exporting final merged FBX...")
print(f"Output: {OUTPUT_FBX}")

# Ensure output directory exists
os.makedirs(os.path.dirname(OUTPUT_FBX), exist_ok=True)

export_start = time.time()
bpy.ops.export_scene.fbx(
    filepath=OUTPUT_FBX,
    use_selection=True,
    apply_unit_scale=True,
    path_mode='COPY',
    embed_textures=True,
    bake_anim=False
)
export_time = time.time() - export_start

print(f"Export completed in {format_time(export_time)}")

# ---------------- DONE ----------------
total_time = time.time() - start_time
print()
print("=" * 60)
print("Final Merge Complete!")
print("=" * 60)
print(f"Total time: {format_time(total_time)}")
print(f"Output file: {OUTPUT_FBX}")

# Check file size
if os.path.exists(OUTPUT_FBX):
    file_size_mb = os.path.getsize(OUTPUT_FBX) / (1024 * 1024)
    print(f"File size: {file_size_mb:.2f} MB")

print("=" * 60)
