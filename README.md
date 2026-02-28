# 🌍 Google Earth → MSFS Pipeline

A batch processing pipeline that converts Google Earth Studio GLTF exports into optimized FBX assets for Microsoft Flight Simulator, with a dark-themed GUI manager for configuration and execution.

---

## Overview

Google Earth Studio can export 3D city/terrain captures as GLTF files, but MSFS requires optimized FBX. This pipeline automates the full conversion:

```
GLTF exports  →  Batch decimation & normal baking  →  Batch FBX files  →  Single merged FBX
     (raw)              (Blender, parallel)                                    (MSFS-ready)
```

Each stage runs inside Blender headlessly. The GUI wraps the entire workflow so you never need to touch a terminal.

---

## Project Structure

```
google_earth_export/
│
├── pipeline_manager.py          # GUI application — run this
├── config.json                  # All pipeline settings (auto-saved by GUI)
│
├── run_full_pipeline.ps1        # Master orchestrator (Step 0.5 → 1 → 2)
├── process_gltf_parallel.ps1   # Step 1: parallel Blender batch jobs
│
├── merge_gltf_batch_optimized.py  # Blender script: decimate + bake per batch
├── merge_final_fbx.py             # Blender script: merge all batch FBX → one
│
└── gltf_export/
    ├── modelLib/                # Input: your GLTF files (*_LOD00.gltf)
    │   └── texture/             # Input: diffuse textures (.png / .jpg)
    ├── batch_fbx/               # Intermediate: one FBX per batch + logs
    └── merged/
        └── merged.fbx           # Final output
```

---

## Requirements

| Requirement | Version |
|---|---|
| Windows | 10 or 11 (64-bit) |
| Python | 3.8+ |
| Blender | 4.x or 5.x |
| PowerShell | 5.1+ (included in Windows) |

> **No extra Python packages needed.** The GUI uses only the standard library (`tkinter`, `subprocess`, `threading`, `json`).

---

## Quick Start

### 1. Place your files

Copy all pipeline scripts into your project root (the same folder as `config.json`):

```
D:\Projects\google_earth_export\
├── pipeline_manager.py
├── config.json
├── run_full_pipeline.ps1
├── process_gltf_parallel.ps1
├── merge_gltf_batch_optimized.py
└── merge_final_fbx.py
```

Put your Google Earth Studio GLTF exports in:
```
gltf_export\modelLib\          ← *_LOD00.gltf files go here
gltf_export\modelLib\texture\  ← corresponding textures go here
```

### 2. Launch the GUI

```powershell
python pipeline_manager.py
```

### 3. Configure paths

In the **Configuration** tab:
- Set **Project Root** to your project folder (e.g. `D:\Projects\google_earth_export\`)
- Set **Blender Executable** to your Blender install (e.g. `D:\Program Files\Blender 5.0\blender.exe`)
- Click **Save** in the top bar

### 4. Run the pipeline

Switch to the **Pipeline Runner** tab and click **▶ Run Pipeline**.

---

## Pipeline Stages

### Step 0.5 — Texture Consolidation
Scans `modelLib\texture\` and moves all texture files up to `modelLib\`. Identical duplicates (MD5-matched) are removed; conflicting filenames are auto-renamed `filename_1.png`, `filename_2.png`, etc. Optionally removes the now-empty `texture\` subdirectory.

### Step 1 — Parallel Batch Processing (`process_gltf_parallel.ps1`)
- Finds all `*_LOD00.gltf` files in `modelLib\`
- Splits them into batches (default: 10 files per batch)
- Launches up to N Blender instances in parallel (default: 32)
- Each Blender instance runs `merge_gltf_batch_optimized.py`:
  - Imports all GLTF files in the batch
  - Applies **mesh decimation** (reduces polygon count by the decimate ratio)
  - Bakes **normal maps** from high-poly → low-poly using Cycles
  - Joins all meshes and exports as `batch_XXXX.fbx`
- Stdout and stderr for each batch are saved as `.log` / `.err` files

### Step 2 — Final Merge (`merge_final_fbx.py`)
- Imports all `batch_*.fbx` files from the batch output folder
- Deduplicates materials by name
- Joins everything into a single mesh object
- Exports as `merged.fbx` with embedded textures

---

## GUI Reference

### ⚙️ Configuration Tab

All fields map directly to `config.json`. Changes are auto-saved when you click **Run Pipeline**, or manually with the **Save** button.

| Section | Key Settings |
|---|---|
| **Paths** | Project root directory, Blender executable path |
| **Folders** | Relative paths for each pipeline stage's input/output |
| **Scripts** | Filenames of the PowerShell and Python scripts |
| **Processing** | Parallel instances, batch size, decimate ratio, check interval |
| **Optimization** | Enable/disable decimation and normal baking, map resolution, bake cage settings |
| **Options** | Clean output folders, verbose logging, save batch logs, remove high-poly after bake |
| **Quality Presets** | Editable preset table (Ultra High → Very Low) |

### 🚀 Pipeline Runner Tab

**Run options** (map to PowerShell switches):

| Checkbox | PowerShell Flag | Effect |
|---|---|---|
| Skip Batch Processing | `-SkipBatchProcessing` | Skips Step 1; uses existing batch FBX files |
| Skip Texture Consolidation | `-SkipTextureConsolidation` | Skips Step 0.5 |
| Only Final Merge | `-OnlyFinalMerge` | Runs Step 2 only |

**Override fields** — leave blank to use config defaults, or enter values to override for this run only:
- **Files/Batch** — how many GLTF files per Blender instance
- **Decimate** — polygon reduction ratio (0.0–1.0)

**Quick Preset buttons** — fill in the override fields from a named quality preset instantly.

**Console** — live-streamed output with color coding:

| Color | Meaning |
|---|---|
| 🟢 Green | Completion / success messages |
| 🔵 Blue | Step headers / progress info |
| 🟡 Yellow | Warnings / skipped files |
| 🔴 Red | Errors / failed imports |
| 🟣 Purple | Section separators |
| Gray | Timestamps |

**Stop** — sends `taskkill /F /T` to terminate the PowerShell process and all child Blender processes.

**Save Log** — exports the full console contents to a `.txt` file.

### 📊 Batch Monitor Tab

Watches the `batch_fbx\` output directory while the pipeline runs. Shows a live file table with size, modification time, and status badge (✅ FBX / 📋 Log / ⚠ Error). Summary stat cards display total files, FBX count, log count, error count, and total size on disk.

Click **▶ Watch** to auto-refresh every 3 seconds, or **↻ Refresh** for a one-shot update.

---

## Quality Presets

| Preset | Decimate Ratio | Files / Batch | Normal Map Res |
|---|---|---|---|
| Ultra High | 0.9 | 5 | 4096 × 4096 |
| High | 0.7 | 10 | 2048 × 2048 |
| Medium *(default)* | 0.5 | 15 | 2048 × 2048 |
| Low | 0.3 | 20 | 1024 × 1024 |
| Very Low | 0.1 | 50 | 512 × 512 |

Higher decimate ratios preserve more geometry but produce larger files and take longer to process. Lower ratios are faster and produce smaller FBX files at the cost of mesh detail.

---

## Configuration Reference (`config.json`)

```jsonc
{
  "paths": {
    "projectRoot": "D:\\Projects\\google_earth_export\\",
    "blenderExecutable": "D:\\Program Files\\Blender 5.0\\blender.exe"
  },
  "folders": {
    "gltfExport":        "gltf_export",
    "modelLib":          "gltf_export\\modelLib",
    "modelLibTextures":  "gltf_export\\modelLib\\texture",
    "batchFbxOutput":   "gltf_export\\batch_fbx",
    "mergedOutput":     "gltf_export\\merged"
  },
  "scripts": {
    "mergeGltfBatchOptimized": "merge_gltf_batch_optimized.py",
    "mergeFinalFbx":           "merge_final_fbx.py",
    "processGltfParallel":     "process_gltf_parallel.ps1",
    "runFullPipeline":         "run_full_pipeline.ps1"
  },
  "output": {
    "mergedFbxName": "merged.fbx"
  },
  "processing": {
    "maxParallelBlenderInstances": 32,   // How many Blender processes run simultaneously
    "processCheckIntervalMs":      200,  // How often to poll for finished processes (ms)
    "defaultFilesPerBatch":        10,   // GLTF files per Blender instance
    "defaultDecimateRatio":        0.5,  // Polygon reduction (0.1 = aggressive, 0.9 = minimal)
    "cleanupSubfolders":           true  // Remove empty texture/ dir after consolidation
  },
  "optimization": {
    "enableDecimation":    true,
    "enableNormalBaking":  true,
    "normalMapResolution": 2048,   // Width & height of baked normal maps in pixels
    "bakeCageExtrusion":   0.1,    // Blender bake cage extrusion distance
    "bakeMaxRayDistance":  1.0     // Blender bake max ray distance
  },
  "options": {
    "cleanOutputFolders":       false,  // Delete batch_fbx/ and merged/ before each run
    "verboseLogging":           true,
    "saveBatchLogs":            true,   // Save .log and .err per batch
    "removeHighPolyAfterBake":  true    // Delete high-poly duplicate after normal baking
  }
}
```

---

## Running Without the GUI

You can invoke the pipeline directly from PowerShell:

```powershell
# Full pipeline with defaults
.\run_full_pipeline.ps1 -ConfigPath config.json

# Custom batch size and quality
.\run_full_pipeline.ps1 -ConfigPath config.json -FilesPerBatch 5 -DecimateRatio 0.7

# Skip batch processing (re-merge existing batches)
.\run_full_pipeline.ps1 -ConfigPath config.json -SkipBatchProcessing

# Final merge only
.\run_full_pipeline.ps1 -ConfigPath config.json -OnlyFinalMerge

# Batch processing only (no final merge)
.\process_gltf_parallel.ps1 -ConfigPath config.json -FilesPerBatch 10 -DecimateRatio 0.5
```

---

## Threading Model

The GUI uses four threads to stay responsive at all times:

| Thread | Responsibility |
|---|---|
| **UI thread** | Tkinter mainloop — never blocked |
| **Pipeline thread** | Launches `run_full_pipeline.ps1` via `subprocess.Popen` |
| **Stdout reader** | Streams lines from the process into a `queue.Queue` |
| **Monitor watcher** | Polls the batch output directory every 3 seconds (optional) |

The UI thread drains the queue every 50 ms with `after()`, so console output appears in real time without freezing the interface.

---

## Troubleshooting

**"Blender executable not found"**
Check the `blenderExecutable` path in config. Use the full absolute path including the `.exe` extension.

**"No GLTF files found"**
GLTF files must match the pattern `*_LOD00.gltf` and be placed directly in `modelLib\` (not in subdirectories).

**Pipeline stops with exit code 1**
Check the `.err` files in `batch_fbx\` — they contain Blender's stderr for the failing batch. Common causes: out of memory (reduce `filesPerBatch`), corrupted GLTF, missing texture directory.

**Normal baking is very slow**
Normal baking uses Cycles, which is GPU-accelerated. Make sure Blender's preferences have your GPU selected under **Edit → Preferences → System → Cycles Render Devices**. Alternatively, disable `enableNormalBaking` in config for faster runs without baked normals.

**Too many parallel Blender instances**
Each Blender instance loads all GLTF meshes into memory. If you hit RAM limits, reduce `maxParallelBlenderInstances` (try 4–8) and/or reduce `defaultFilesPerBatch`.

**Scrolling jumps to top/bottom in the GUI**
This was a known bug (fixed): multiple widgets catching the same scroll event simultaneously. If it recurs, hover directly over the scrollbar and drag instead.

---

## License

MIT — do whatever you want with it.
