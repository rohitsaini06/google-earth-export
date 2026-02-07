import bpy
import sys
import os

# Parse arguments
argv = sys.argv
argv = argv[argv.index("--") + 1:]

GLTF_FILES = argv[0].split("|")  # Pipe-separated list of GLTF paths
TEXTURE_DIR = argv[1]
OUTPUT_FBX = argv[2]
DECIMATE_RATIO = float(argv[3]) if len(argv) > 3 else 0.5

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def import_gltf(path):
    """Import a single GLTF file"""
    try:
        bpy.ops.import_scene.gltf(filepath=path)
        return True
    except Exception as e:
        print(f"ERROR importing {path}: {e}")
        return False

def find_texture(base_name, texture_dir):
    """Find texture file for a given base name"""
    for ext in (".png", ".jpg", ".jpeg"):
        texture_path = os.path.join(texture_dir, base_name + ext)
        if os.path.exists(texture_path):
            return texture_path
    return None

def create_normal_bake_material(obj, diffuse_texture_path):
    """Create material with diffuse texture for normal baking"""
    mat = bpy.data.materials.new(name=f"Mat_{obj.name}")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    # Create nodes
    tex_node = nodes.new("ShaderNodeTexImage")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    out = nodes.new("ShaderNodeOutputMaterial")

    # Load diffuse texture
    if diffuse_texture_path and os.path.exists(diffuse_texture_path):
        tex_node.image = bpy.data.images.load(diffuse_texture_path, check_existing=True)

    # Connect nodes
    links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    # Assign material
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    
    return mat

def decimate_and_bake(obj, decimate_ratio, texture_dir):
    """Decimate mesh and bake normal map from high poly"""
    if obj.type != 'MESH':
        return
    
    # Get base name for texture lookup
    base_name = os.path.splitext(obj.name.rsplit('.', 1)[0])[0]
    diffuse_texture = find_texture(base_name, texture_dir)
    
    # Store original mesh
    high_poly_mesh = obj.data.copy()
    high_poly_obj = bpy.data.objects.new(f"{obj.name}_highpoly", high_poly_mesh)
    bpy.context.collection.objects.link(high_poly_obj)
    high_poly_obj.location = obj.location
    high_poly_obj.rotation_euler = obj.rotation_euler
    high_poly_obj.scale = obj.scale
    
    # Apply material to both objects
    create_normal_bake_material(obj, diffuse_texture)
    create_normal_bake_material(high_poly_obj, diffuse_texture)
    
    # Decimate the low poly version
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    
    modifier = obj.modifiers.new(name="Decimate", type='DECIMATE')
    modifier.ratio = decimate_ratio
    modifier.use_collapse_triangulate = True
    
    # Apply modifier
    bpy.ops.object.modifier_apply(modifier="Decimate")
    
    # Prepare for baking
    # Create UV map if doesn't exist
    if not obj.data.uv_layers:
        bpy.ops.mesh.uv_texture_add()
    
    # Create normal map image
    normal_map_name = f"{base_name}_normal"
    normal_img = bpy.data.images.new(normal_map_name, width=2048, height=2048, alpha=False)
    
    # Add image texture node for baking
    mat = obj.data.materials[0]
    nodes = mat.node_tree.nodes
    
    bake_node = nodes.new("ShaderNodeTexImage")
    bake_node.image = normal_img
    bake_node.name = "BakeTarget"
    nodes.active = bake_node
    
    # Select both objects for baking
    bpy.ops.object.select_all(action='DESELECT')
    high_poly_obj.select_set(True)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    
    # Bake normal map
    try:
        bpy.context.scene.render.engine = 'CYCLES'
        bpy.context.scene.cycles.bake_type = 'NORMAL'
        bpy.context.scene.render.bake.use_selected_to_active = True
        bpy.context.scene.render.bake.cage_extrusion = 0.1
        bpy.context.scene.render.bake.max_ray_distance = 1.0
        
        bpy.ops.object.bake(type='NORMAL')
        
        # Save normal map
        normal_map_path = os.path.join(texture_dir, f"{normal_map_name}.png")
        normal_img.filepath_raw = normal_map_path
        normal_img.file_format = 'PNG'
        normal_img.save()
        
        # Connect normal map to material
        normal_map_node = nodes.new("ShaderNodeNormalMap")
        normal_tex_node = nodes.new("ShaderNodeTexImage")
        normal_tex_node.image = normal_img
        
        bsdf = None
        for node in nodes:
            if node.type == 'BSDF_PRINCIPLED':
                bsdf = node
                break
        
        if bsdf:
            mat.node_tree.links.new(normal_tex_node.outputs["Color"], normal_map_node.inputs["Color"])
            mat.node_tree.links.new(normal_map_node.outputs["Normal"], bsdf.inputs["Normal"])
        
    except Exception as e:
        print(f"WARNING: Failed to bake normal map for {obj.name}: {e}")
    
    # Clean up high poly mesh
    bpy.data.objects.remove(high_poly_obj)
    bpy.data.meshes.remove(high_poly_mesh)

def main():
    print(f"Processing {len(GLTF_FILES)} GLTF files")
    print(f"Decimate ratio: {DECIMATE_RATIO}")
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
    
    print(f"Successfully imported {imported_count}/{len(GLTF_FILES)} files")
    
    # Collect all mesh objects
    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    print(f"Found {len(mesh_objects)} mesh objects")
    
    # Decimate and bake each object
    if os.path.exists(TEXTURE_DIR):
        for idx, obj in enumerate(mesh_objects, 1):
            print(f"Processing {idx}/{len(mesh_objects)}: {obj.name}")
            decimate_and_bake(obj, DECIMATE_RATIO, TEXTURE_DIR)
    else:
        print(f"WARNING: Texture directory not found: {TEXTURE_DIR}")
    
    # Select all mesh objects for export
    bpy.ops.object.select_all(action='DESELECT')
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH':
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
    
    # Join all meshes
    if len([obj for obj in bpy.context.scene.objects if obj.type == 'MESH']) > 0:
        print("Joining all meshes")
        bpy.ops.object.join()
    
    # Export to FBX
    print(f"Exporting to {OUTPUT_FBX}")
    os.makedirs(os.path.dirname(OUTPUT_FBX), exist_ok=True)
    
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
