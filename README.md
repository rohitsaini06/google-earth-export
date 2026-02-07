# Google Earth Export to 3ds Max Reference Pipeline

Automated processing pipeline for converting Google Earth GLTF exports into optimized, merged FBX files for use as reference models in 3ds Max for detailed 3D map creation.

## 🎯 What This Pipeline Does

Transforms hundreds or thousands of individual GLTF models into a single, optimized FBX file that can be imported into 3ds Max as a reference for manual 3D modeling and map creation.

The pipeline performs:

1. **Texture Consolidation** - Organizes all textures into a single directory
2. **Parallel Batch Processing** - Converts GLTF files to optimized FBX batches using multiple Blender instances
3. **Mesh Optimization** - Decimates geometry and bakes normal maps to preserve detail while reducing file size
4. **Final Merge** - Combines all batch files into a single FBX that can be imported into 3ds Max as a reference model

**Use Case**: The final merged FBX serves as an accurate 3D reference of real-world terrain and buildings, allowing you to manually create detailed, optimized 3D maps in 3ds Max.

## 📋 Prerequisites

- **earth2msfs** - Download 3D map tiles from Google Earth: [Google Earth Decoder Update](https://flightsim.to/file/39900/gogole-earth-decoder-update)
- **Blender 4.0+** (tested with Blender 5.0)
- **PowerShell 5.1+** (Windows)
- **Storage**: Adequate disk space for temporary files (typically 2-3x the source size)
- **RAM**: 16GB+ recommended for large datasets

## 🗺️ Getting Google Earth Tiles

Before using this pipeline, you need to download 3D map tiles using **earth2msfs**:

1. Download [Google Earth Decoder Update](https://flightsim.to/file/39900/gogole-earth-decoder-update)
2. Launch the application
3. Select your desired map area
4. Download the 3D tiles (GLTF format)
5. The app will export files to a folder structure compatible with this pipeline

## 🚀 Quick Start

### 1. Configure Paths

Edit `config.json` and update these paths:

```json
{
  "paths": {
    "projectRoot": "D:\\Projects\\google_earth_export\\",
    "blenderExecutable": "D:\\Program Files\\Blender 5.0\\blender.exe"
  }
}
```

### 2. Organize Your Files

Place your Google Earth export in this structure:

```
D:\Projects\google_earth_export\
└── gltf_export\
    └── modelLib\
        ├── model_001_LOD00.gltf
        ├── model_002_LOD00.gltf
        ├── ...
        └── texture\
            ├── texture_001.png
            ├── texture_002.jpg
            └── ...
```

### 3. Run the Pipeline

```powershell
.\run_full_pipeline.ps1 -FilesPerBatch 10 -DecimateRatio 0.5
```

## 📊 Pipeline Workflow

```
┌─────────────────────────────────────────────────────────┐
│ Step 0.5: Texture Consolidation                         │
│ • Moves textures from subfolders to modelLib root       │
│ • Handles duplicate detection (MD5 hash)                │
│ • Renames conflicts automatically                       │
│ • Cleans empty directories                              │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ Step 1: Parallel Batch Processing                       │
│ • Groups GLTF files into batches                        │
│ • Runs multiple Blender instances simultaneously        │
│ • Each batch: GLTF → Optimized FBX                      │
│ • Applies mesh decimation                               │
│ • Bakes normal maps from high-poly geometry             │
│ • Embeds textures in FBX files                          │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ Step 2: Final Merge                                     │
│ • Imports all batch FBX files                           │
│ • Removes duplicate materials                           │
│ • Joins all meshes into single object                   │
│ • Exports final merged FBX                              │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ Import to 3ds Max                                       │
│ • Use merged.fbx as reference model                     │
│ • Trace/rebuild geometry with optimized topology        │
│ • Create detailed materials and textures                │
│ • Build game-ready or production assets                 │
└─────────────────────────────────────────────────────────┘
```

## 🎨 Using the Output in 3ds Max

Once the pipeline completes, you'll have a `merged.fbx` file ready for 3ds Max:

1. **Import as Reference**: 
   - File → Import → Select `merged.fbx`
   - Use as visual reference for accurate terrain and building placement

2. **Manual Modeling**:
   - Trace over the reference geometry with clean topology
   - Create optimized LODs (Level of Detail) models
   - Build proper UV maps for texturing

3. **Benefits**:
   - Accurate real-world proportions and locations
   - Consolidated single-file reference (easier to manage than thousands of files)
   - Optimized geometry won't slow down 3ds Max viewport
   - Embedded textures provide visual context

## ⚙️ Configuration Guide

### Quality Presets

Use predefined quality presets for common scenarios:

| Preset | Decimate Ratio | Files/Batch | Normal Map | Use Case |
|--------|----------------|-------------|------------|----------|
| `ultra_high` | 0.9 | 5 | 4096px | High-detail reference, architectural work |
| `high` | 0.7 | 10 | 2048px | Detailed reference, quality modeling |
| `medium` | 0.5 | 15 | 2048px | **Default**, balanced reference |
| `low` | 0.3 | 20 | 1024px | Quick reference, fast viewport |
| `very_low` | 0.1 | 50 | 512px | Preview/layout only |

**Example using preset values:**
```powershell
.\run_full_pipeline.ps1 -FilesPerBatch 5 -DecimateRatio 0.9  # Ultra high quality
```

### Key Parameters

#### Files Per Batch (`-FilesPerBatch`)
- **Default**: 10
- **Range**: 1-100
- **Impact**: 
  - Lower = More batches, less memory per process
  - Higher = Fewer batches, faster total time, more memory

#### Decimate Ratio (`-DecimateRatio`)
- **Default**: 0.5 (50% of original geometry)
- **Range**: 0.1-1.0
- **Impact**:
  - 1.0 = No decimation (original geometry)
  - 0.5 = Half the polygons
  - 0.1 = 10% of polygons (aggressive)

#### Max Parallel Instances
- **Default**: 32
- **Set in**: `config.json` → `processing.maxParallelBlenderInstances`
- **Recommendation**: Number of CPU cores × 2

## 🔧 Advanced Usage

### Skip Steps

```powershell
# Use existing batch files, only run final merge
.\run_full_pipeline.ps1 -SkipBatchProcessing

# Skip texture consolidation (textures already organized)
.\run_full_pipeline.ps1 -SkipTextureConsolidation

# Only run final merge (skip Steps 0.5 and 1)
.\run_full_pipeline.ps1 -OnlyFinalMerge
```

### Clean Output Folders

Enable in `config.json`:
```json
{
  "options": {
    "cleanOutputFolders": true
  }
}
```

This deletes previous batch and merged files before processing.

### Custom Quality Settings

Directly specify optimization parameters:

```powershell
# Maximum quality preservation
.\run_full_pipeline.ps1 -DecimateRatio 0.95 -FilesPerBatch 3

# Fast preview processing
.\run_full_pipeline.ps1 -DecimateRatio 0.1 -FilesPerBatch 50
```

## 📁 Output Structure

```
gltf_export\
├── batch_fbx\               # Step 1 output
│   ├── batch_0001.fbx
│   ├── batch_0002.fbx
│   ├── batch_0001.log      # Process logs
│   └── ...
└── merged\                  # Final output
    └── merged.fbx          # Final merged file
```

## 🎨 Optimization Features

### Mesh Decimation
- Reduces polygon count while preserving shape
- Ratio of 0.5 = 50% fewer polygons
- Applied before normal baking

### Normal Map Baking
- **Purpose**: Preserve high-poly detail on low-poly mesh
- **Resolution**: 2048×2048 (configurable)
- **Process**:
  1. Original mesh saved as high-poly reference
  2. Mesh decimated to target ratio
  3. Normal map baked from high-poly to low-poly
  4. Normal map applied to material
  5. High-poly reference deleted

### Material Optimization
- Removes duplicate materials by name
- Consolidates material slots
- Preserves texture references

### Texture Consolidation
- **Duplicate Detection**: MD5 hash comparison
- **Conflict Resolution**: Automatic renaming (texture_1.png, texture_2.png)
- **Supported Formats**: PNG, JPG, JPEG, TGA, BMP, TIFF, DDS

## 📈 Performance

### Typical Processing Times

| Dataset Size | Files | Step 1 (32 cores) | Step 2 | Total |
|--------------|-------|-------------------|--------|-------|
| Small | 100 | 5-10 min | 2 min | 7-12 min |
| Medium | 500 | 15-30 min | 5 min | 20-35 min |
| Large | 2000+ | 1-2 hours | 15 min | 1.5-2.5 hrs |

*Times vary based on CPU, file complexity, and quality settings*

### Performance Optimization Tips

1. **Use all CPU cores**: Set `maxParallelBlenderInstances` to your core count × 2
2. **SSD storage**: Run from SSD for 2-3x faster I/O
3. **Batch size tuning**: 
   - More cores → Increase `FilesPerBatch`
   - Low RAM → Decrease `FilesPerBatch`
4. **Skip redundant steps**: Use `-SkipTextureConsolidation` if already done

## 🔍 Troubleshooting

### "No GLTF files found"
- Verify files are named `*_LOD00.gltf`
- Check `modelLib` directory path in config

### "Blender executable not found"
- Update `blenderExecutable` path in `config.json`
- Ensure Blender is installed

### "Out of memory" errors
- Reduce `FilesPerBatch` (try 5 or lower)
- Reduce `maxParallelBlenderInstances`
- Close other applications

### Texture paths broken
- Run Step 0.5 texture consolidation
- Ensure textures are in `modelLib` root, not subfolders

### Slow processing
- Check CPU usage (should be near 100% during Step 1)
- Verify using SSD storage
- Increase `FilesPerBatch` if CPU underutilized

## 📝 Configuration Reference

### `config.json` Structure

```json
{
  "paths": {
    "projectRoot": "D:\\Projects\\google_earth_export\\",
    "blenderExecutable": "D:\\Program Files\\Blender 5.0\\blender.exe"
  },
  "processing": {
    "maxParallelBlenderInstances": 32,    // Concurrent Blender processes
    "processCheckIntervalMs": 200,        // Job polling interval
    "defaultFilesPerBatch": 10,           // Default batch size
    "defaultDecimateRatio": 0.5,          // Default decimation
    "cleanupSubfolders": true             // Remove empty dirs after consolidation
  },
  "optimization": {
    "enableDecimation": true,             // Enable mesh decimation
    "enableNormalBaking": true,           // Enable normal map baking
    "normalMapResolution": 2048,          // Normal map size
    "bakeCageExtrusion": 0.1,             // Bake cage offset
    "bakeMaxRayDistance": 1.0             // Max ray distance for baking
  },
  "options": {
    "cleanOutputFolders": false,          // Delete previous outputs
    "verboseLogging": true,               // Detailed console output
    "saveBatchLogs": true,                // Save process logs
    "removeHighPolyAfterBake": true       // Delete high-poly after baking
  }
}
```

## 🎯 Common Workflows

### First Time Setup
```powershell
# 1. Download map tiles with earth2msfs
# 2. Edit config.json with your paths
# 3. Run full pipeline with default settings
.\run_full_pipeline.ps1
# 4. Import merged.fbx into 3ds Max as reference
```

### Re-process with Different Quality
```powershell
# Use existing batches, just re-merge with different settings
.\run_full_pipeline.ps1 -SkipBatchProcessing -OnlyFinalMerge
```

### Process New Textures Only
```powershell
# Only consolidate textures, skip processing
.\run_full_pipeline.ps1 -SkipBatchProcessing -OnlyFinalMerge
```

### Maximum Quality Reference for Architectural Work
```powershell
# Ultra-high quality for detailed modeling reference
.\run_full_pipeline.ps1 -FilesPerBatch 3 -DecimateRatio 0.95
```

### Quick Layout Reference
```powershell
# Fast low-quality for viewport layout and planning
.\run_full_pipeline.ps1 -FilesPerBatch 50 -DecimateRatio 0.1
```

## 📦 File Descriptions

| File | Purpose |
|------|---------|
| `config.json` | Main configuration file |
| `run_full_pipeline.ps1` | Master orchestration script |
| `process_gltf_parallel.ps1` | Parallel batch processor |
| `merge_gltf_batch_optimized.py` | Blender batch optimization script |
| `merge_final_fbx.py` | Blender final merge script |

## ⚠️ Important Notes

- **Backup your data**: Always keep original GLTF files
- **Reference model**: The final FBX is meant for reference, not direct game/production use
- **Manual modeling**: Use the merged FBX as a guide to create optimized models in 3ds Max
- **Texture paths**: Pipeline expects textures in `modelLib` or `modelLib\texture`
- **GLTF naming**: Files must end with `_LOD00.gltf` to be processed
- **Embedded textures**: Final FBX embeds all textures (increases file size but simplifies import)
- **Progress monitoring**: Watch console for real-time progress updates

## 🤝 Support

For issues or questions:
1. Check troubleshooting section above
2. Review log files in `batch_fbx\batch_*.log`
3. Verify config.json paths are correct
4. Ensure sufficient disk space and memory

## 📄 License

This pipeline is provided as-is for processing Google Earth Studio exports into 3ds Max reference models.
