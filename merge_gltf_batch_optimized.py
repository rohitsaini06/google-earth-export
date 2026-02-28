import bpy
import sys
import os

# Parse arguments passed after "--"
argv = sys.argv
argv = argv[argv.index("--") + 1:]

GLTF_FILES       = argv[0].split("|")          # Pipe-separated GLTF paths
TEXTURE_DIR      = argv[1]
OUTPUT_FBX       = argv[2]
DECIMATE_RATIO   = float(argv[3]) if len(argv) > 3 else 0.5

# BUG FIX: these were hardcoded; now read from CLI args passed by process_gltf_parallel.ps1
NORMAL_MAP_RES   = int(argv[4])   if len(argv) > 4 else 2048
CAGE_EXTRUSION   = float(argv[5]) if len(argv) > 5 else 0.1
MAX_RAY_DISTANCE = float(argv[6]) if len(argv) > 6 else 1.0
ENABLE_DECIMATION   = (argv[7] == "1") if len(argv) > 7 else True
ENABLE_BAKING       = (argv[8] == "1") if len(argv) > 8 else True
REMOVE_HIGH_POLY    = (argv[9] == "1") if len(argv) > 9 else True


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_gltf(path):
    """Import a single GLTF file."""
    try:
        bpy.ops.import_scene.gltf(filepath=path)
        return True
    except Exception as e:
        print(f"ERROR importing {path}: {e}")
        return False


def find_texture(base_name, texture_dir):
    """Find texture file for a given base name."""
    for ext in (".png", ".jpg", ".jpeg"):
        texture_path = os.path.join(texture_dir, base_name + ext)
        if os.path.exists(texture_path):
            return texture_path
    return None


def create_normal_bake_material(obj, diffuse_texture_path):
    """Create material with diffuse texture for normal baking."""
    mat = bpy.data.materials.new(name=f"Mat_{obj.name}")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    tex_node = nodes.new("ShaderNodeTexImage")
    bsdf     = nodes.new("ShaderNodeBsdfPrincipled")
    out      = nodes.new("ShaderNodeOutputMaterial")

    if diffuse_texture_path and os.path.exists(diffuse_texture_path):
        tex_node.image = bpy.data.images.load(diffuse_texture_path, check_existing=True)

    links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return mat


def decimate_and_bake(obj):
    """
    Conditionally decimate mesh and bake normal map based on config flags.
    All parameters come from module-level constants parsed from CLI args.
    """
    if obj.type != 'MESH':
        return

    base_name        = os.path.splitext(obj.name.rsplit('.', 1)[0])[0]
    diffuse_texture  = find_texture(base_name, TEXTURE_DIR)

    # ── Decimation ────────────────────────────────────────────────
    if ENABLE_DECIMATION:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        modifier = obj.modifiers.new(name="Decimate", type='DECIMATE')
        modifier.ratio = DECIMATE_RATIO
        modifier.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier="Decimate")
        print(f"  Decimated {obj.name} (ratio={DECIMATE_RATIO})")
    else:
        print(f"  Decimation skipped for {obj.name} (disabled in config)")

    # ── Normal Baking ─────────────────────────────────────────────
    if not ENABLE_BAKING:
        print(f"  Normal baking skipped for {obj.name} (disabled in config)")
        # Still apply a material with the diffuse texture even without baking
        if diffuse_texture:
            create_normal_bake_material(obj, diffuse_texture)
        return

    # Store original high-poly mesh
    high_poly_mesh = obj.data.copy()
    high_poly_obj  = bpy.data.objects.new(f"{obj.name}_highpoly", high_poly_mesh)
    bpy.context.collection.objects.link(high_poly_obj)
    high_poly_obj.location      = obj.location
    high_poly_obj.rotation_euler = obj.rotation_euler
    high_poly_obj.scale         = obj.scale

    create_normal_bake_material(obj, diffuse_texture)
    create_normal_bake_material(high_poly_obj, diffuse_texture)

    # Ensure UV map exists on low-poly
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    if not obj.data.uv_layers:
        bpy.ops.mesh.uv_texture_add()

    # BUG FIX: resolution was hardcoded to 2048; now uses NORMAL_MAP_RES from config
    normal_map_name = f"{base_name}_normal"
    normal_img = bpy.data.images.new(
        normal_map_name,
        width=NORMAL_MAP_RES,
        height=NORMAL_MAP_RES,
        alpha=False
    )

    mat   = obj.data.materials[0]
    nodes = mat.node_tree.nodes

    bake_node       = nodes.new("ShaderNodeTexImage")
    bake_node.image = normal_img
    bake_node.name  = "BakeTarget"
    nodes.active    = bake_node

    bpy.ops.object.select_all(action='DESELECT')
    high_poly_obj.select_set(True)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    try:
        bpy.context.scene.render.engine = 'CYCLES'
        bpy.context.scene.cycles.bake_type = 'NORMAL'
        bpy.context.scene.render.bake.use_selected_to_active = True

        # BUG FIX: were hardcoded to 0.1 / 1.0; now use values from config via CLI
        bpy.context.scene.render.bake.cage_extrusion    = CAGE_EXTRUSION
        bpy.context.scene.render.bake.max_ray_distance  = MAX_RAY_DISTANCE

        bpy.ops.object.bake(type='NORMAL')

        normal_map_path            = os.path.join(TEXTURE_DIR, f"{normal_map_name}.png")
        normal_img.filepath_raw    = normal_map_path
        normal_img.file_format     = 'PNG'
        normal_img.save()
        print(f"  Baked normal map: {normal_map_path}")

        # Wire normal map into the material
        normal_map_node  = nodes.new("ShaderNodeNormalMap")
        normal_tex_node  = nodes.new("ShaderNodeTexImage")
        normal_tex_node.image = normal_img

        bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if bsdf:
            mat.node_tree.links.new(normal_tex_node.outputs["Color"],
                                    normal_map_node.inputs["Color"])
            mat.node_tree.links.new(normal_map_node.outputs["Normal"],
                                    bsdf.inputs["Normal"])

    except Exception as e:
        print(f"WARNING: Failed to bake normal map for {obj.name}: {e}")

    # BUG FIX: was always removing high-poly; now respects removeHighPolyAfterBake config
    if REMOVE_HIGH_POLY:
        bpy.data.objects.remove(high_poly_obj)
        bpy.data.meshes.remove(high_poly_mesh)
        print(f"  Removed high-poly mesh for {obj.name}")
    else:
        print(f"  Kept high-poly mesh for {obj.name} (removeHighPolyAfterBake=false)")


def main():
    print(f"Processing {len(GLTF_FILES)} GLTF files")
    print(f"Decimate ratio:        {DECIMATE_RATIO}  (enabled={ENABLE_DECIMATION})")
    print(f"Normal map resolution: {NORMAL_MAP_RES}  (baking enabled={ENABLE_BAKING})")
    print(f"Cage extrusion:        {CAGE_EXTRUSION}")
    print(f"Max ray distance:      {MAX_RAY_DISTANCE}")
    print(f"Remove high-poly:      {REMOVE_HIGH_POLY}")
    print(f"Output: {OUTPUT_FBX}")

    reset_scene()

    # Import all GLTF files
    imported_count = 0
    for gltf_path in GLTF_FILES:
        if os.path.exists(gltf_path):
            if import_gltf(gltf_path):
                imported_count += 1
        else:
            print(f"WARNING: File not found: {gltf_path}")

    print(f"Imported {imported_count}/{len(GLTF_FILES)} files")

    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    print(f"Found {len(mesh_objects)} mesh objects")

    if os.path.exists(TEXTURE_DIR):
        for idx, obj in enumerate(mesh_objects, 1):
            print(f"Processing {idx}/{len(mesh_objects)}: {obj.name}")
            decimate_and_bake(obj)
    else:
        print(f"WARNING: Texture directory not found: {TEXTURE_DIR}")

    # Select all meshes and join
    bpy.ops.object.select_all(action='DESELECT')
    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    for obj in mesh_objects:
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

    if mesh_objects:
        print("Joining all meshes...")
        bpy.ops.object.join()

    # BUG FIX: os.makedirs crashes with empty string if OUTPUT_FBX has no directory part
    out_dir = os.path.dirname(OUTPUT_FBX)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    print(f"Exporting to {OUTPUT_FBX}")
    bpy.ops.export_scene.fbx(
        filepath=OUTPUT_FBX,
        use_selection=True,
        apply_unit_scale=True,
        path_mode='COPY',
        embed_textures=True
    )

    print("Done!")


if __name__ == "__main__":
    main()
