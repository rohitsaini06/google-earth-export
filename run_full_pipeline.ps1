# Google Earth Export to MSFS Pipeline
# Automated GLTF → Optimized FBX → Merged FBX workflow

param(
    [string]$ConfigPath = "config.json",
    [int]$FilesPerBatch = 10,
    [float]$DecimateRatio = 0.5,
    [switch]$SkipBatchProcessing,
    [switch]$SkipTextureConsolidation,
    [switch]$OnlyFinalMerge
)

$ErrorActionPreference = "Stop"

# ============================================
# CONFIGURATION LOADING
# ============================================
Write-Host "Loading configuration from $ConfigPath..." -ForegroundColor Cyan
$config = Get-Content $ConfigPath | ConvertFrom-Json

$projectRoot = $config.paths.projectRoot
$blenderExe = $config.paths.blenderExecutable
$modelLibDir = Join-Path $projectRoot $config.folders.modelLib
$textureSubDir = Join-Path $modelLibDir "texture"
$batchOutputDir = Join-Path $projectRoot $config.folders.batchFbxOutput
$finalOutputDir = Join-Path $projectRoot $config.folders.mergedOutput
$finalOutputFbx = Join-Path $finalOutputDir $config.output.mergedFbxName

# Verify Blender exists
if (-not (Test-Path $blenderExe)) {
    Write-Host "ERROR: Blender executable not found at: $blenderExe" -ForegroundColor Red
    exit 1
}

Write-Host "Blender found: $blenderExe" -ForegroundColor Green
Write-Host ""

# ============================================
# STEP 0.5: TEXTURE CONSOLIDATION
# ============================================
if (-not $SkipTextureConsolidation -and -not $OnlyFinalMerge) {
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host "STEP 0.5: Texture Consolidation" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""
    
    if (-not (Test-Path $modelLibDir)) {
        Write-Host "WARNING: modelLib directory not found: $modelLibDir" -ForegroundColor Yellow
        Write-Host "Skipping texture consolidation..." -ForegroundColor Yellow
        Write-Host ""
    } else {
        $step05StartTime = Get-Date
        
        # Statistics tracking
        $movedCount = 0
        $skippedCount = 0
        $duplicateCount = 0
        $errorCount = 0
        
        # Consolidate textures from subfolder
        if (Test-Path $textureSubDir) {
            Write-Host "Processing texture subfolder..." -ForegroundColor Yellow
            
            $textureFiles = Get-ChildItem -Path $textureSubDir -File -Recurse | Where-Object {
                $_.Extension -match '\.(png|jpg|jpeg|tga|bmp|tiff|dds)$'
            }
            
            Write-Host "Found $($textureFiles.Count) texture files" -ForegroundColor Cyan
            
            foreach ($file in $textureFiles) {
                $targetPath = Join-Path $modelLibDir $file.Name
                
                try {
                    if (Test-Path $targetPath) {
                        # File exists, check if identical
                        $sourceHash = (Get-FileHash -Path $file.FullName -Algorithm MD5).Hash
                        $targetHash = (Get-FileHash -Path $targetPath -Algorithm MD5).Hash
                        
                        if ($sourceHash -eq $targetHash) {
                            # Identical - remove duplicate
                            Remove-Item -Path $file.FullName -Force
                            $skippedCount++
                        } else {
                            # Different file - rename to avoid conflict
                            $baseName = [System.IO.Path]::GetFileNameWithoutExtension($file.Name)
                            $extension = $file.Extension
                            $counter = 1
                            
                            do {
                                $newName = "${baseName}_${counter}${extension}"
                                $targetPath = Join-Path $modelLibDir $newName
                                $counter++
                            } while (Test-Path $targetPath)
                            
                            Move-Item -Path $file.FullName -Destination $targetPath -Force
                            $duplicateCount++
                            Write-Host "  Renamed conflict: $($file.Name) → $newName" -ForegroundColor Yellow
                        }
                    } else {
                        # Move file to root
                        Move-Item -Path $file.FullName -Destination $targetPath -Force
                        $movedCount++
                    }
                } catch {
                    Write-Host "  ERROR moving $($file.Name): $_" -ForegroundColor Red
                    $errorCount++
                }
            }
            
            # Clean up empty directories
            if ($config.processing.cleanupSubfolders) {
                Write-Host "Cleaning up empty subdirectories..." -ForegroundColor Yellow
                
                $remainingFiles = Get-ChildItem -Path $textureSubDir -Recurse -File
                
                if ($remainingFiles.Count -eq 0) {
                    try {
                        Remove-Item -Path $textureSubDir -Recurse -Force
                        Write-Host "  Removed empty texture directory" -ForegroundColor Green
                    } catch {
                        Write-Host "  WARNING: Could not remove texture directory: $_" -ForegroundColor Yellow
                    }
                }
            }
        }
        
        $step05Time = (Get-Date) - $step05StartTime
        
        # Display summary
        Write-Host ""
        Write-Host "Consolidation Summary:" -ForegroundColor Cyan
        Write-Host "  Moved to root:       $movedCount" -ForegroundColor Green
        Write-Host "  Skipped (duplicate): $skippedCount" -ForegroundColor Yellow
        Write-Host "  Renamed (conflict):  $duplicateCount" -ForegroundColor Yellow
        Write-Host "  Errors:              $errorCount" -ForegroundColor $(if ($errorCount -gt 0) { "Red" } else { "Green" })
        Write-Host ""
        Write-Host "Step 0.5 completed in $($step05Time.ToString('hh\:mm\:ss'))" -ForegroundColor Green
        Write-Host ""
    }
}

# ============================================
# STEP 1: BATCH PROCESSING (GLTF → FBX)
# ============================================
if (-not $OnlyFinalMerge) {
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host "STEP 1: Batch Processing GLTF Files" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""
    
    $step1Script = Join-Path $projectRoot $config.scripts.processGltfParallel
    
    if (-not (Test-Path $step1Script)) {
        Write-Host "ERROR: $($config.scripts.processGltfParallel) not found" -ForegroundColor Red
        exit 1
    }
    
    if ($SkipBatchProcessing) {
        Write-Host "Skipping batch processing (using existing batch FBX files)..." -ForegroundColor Yellow
        Write-Host ""
    } else {
        # Clean batch output directory if configured
        if ($config.options.cleanOutputFolders -and (Test-Path $batchOutputDir)) {
            Write-Host "Cleaning batch output directory..." -ForegroundColor Yellow
            Remove-Item -Path $batchOutputDir -Recurse -Force
            Write-Host "Cleaned." -ForegroundColor Green
            Write-Host ""
        }
        
        $step1StartTime = Get-Date
        
        & powershell.exe -ExecutionPolicy Bypass -File $step1Script `
            -ConfigPath $ConfigPath `
            -FilesPerBatch $FilesPerBatch `
            -DecimateRatio $DecimateRatio
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: Batch processing failed" -ForegroundColor Red
            exit 1
        }
        
        $step1Time = (Get-Date) - $step1StartTime
        Write-Host ""
        Write-Host "Step 1 completed in $($step1Time.ToString('hh\:mm\:ss'))" -ForegroundColor Green
        Write-Host ""
    }
    
    # Verify batch files exist
    $batchFiles = Get-ChildItem -Path $batchOutputDir -Filter "batch_*.fbx" -ErrorAction SilentlyContinue
    if (-not $batchFiles -or $batchFiles.Count -eq 0) {
        Write-Host "ERROR: No batch FBX files found in $batchOutputDir" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Found $($batchFiles.Count) batch FBX files ready for final merge" -ForegroundColor Green
    
    # Calculate total size
    $totalSizeMB = ($batchFiles | Measure-Object -Property Length -Sum).Sum / 1MB
    Write-Host "Total batch files size: $([Math]::Round($totalSizeMB, 2)) MB" -ForegroundColor Cyan
    Write-Host ""
}

# ============================================
# STEP 2: FINAL MERGE (Batch FBX → Single FBX)
# ============================================
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "STEP 2: Final FBX Merge" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$mergePythonScript = Join-Path $projectRoot $config.scripts.mergeFinalFbx

if (-not (Test-Path $mergePythonScript)) {
    Write-Host "ERROR: Merge script not found: $mergePythonScript" -ForegroundColor Red
    exit 1
}

# Verify batch directory exists
if (-not (Test-Path $batchOutputDir)) {
    Write-Host "ERROR: Batch output directory not found: $batchOutputDir" -ForegroundColor Red
    Write-Host "Run batch processing first or check the path" -ForegroundColor Yellow
    exit 1
}

# Clean final output directory if configured
if ($config.options.cleanOutputFolders -and (Test-Path $finalOutputDir)) {
    Write-Host "Cleaning final output directory..." -ForegroundColor Yellow
    Remove-Item -Path (Join-Path $finalOutputDir "*") -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Cleaned." -ForegroundColor Green
    Write-Host ""
}

# Create output directory
if (-not (Test-Path $finalOutputDir)) {
    New-Item -ItemType Directory -Path $finalOutputDir | Out-Null
}

Write-Host "Starting final merge..." -ForegroundColor Yellow
Write-Host "Input: $batchOutputDir" -ForegroundColor White
Write-Host "Output: $finalOutputFbx" -ForegroundColor White
Write-Host ""

$step2StartTime = Get-Date

# BUG FIX: was Start-Process -Wait which creates a detached process whose stdout
# is NOT captured by the GUI's subprocess pipe. Using & (call operator) instead
# runs Blender inline so output streams through to the GUI console in real time.
$blenderArgs = @(
    "--background",
    "--python", $mergePythonScript,
    "--",
    $batchOutputDir,
    $finalOutputFbx
)

& $blenderExe @blenderArgs
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Host "ERROR: Final merge failed with exit code $exitCode" -ForegroundColor Red
    exit 1
}

$step2Time = (Get-Date) - $step2StartTime

Write-Host ""
Write-Host "Step 2 completed in $($step2Time.ToString('hh\:mm\:ss'))" -ForegroundColor Green
Write-Host ""

# ============================================
# FINAL SUMMARY
# ============================================
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "PIPELINE COMPLETE!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""

if (Test-Path $finalOutputFbx) {
    $finalSizeMB = (Get-Item $finalOutputFbx).Length / 1MB
    Write-Host "Final merged FBX created successfully!" -ForegroundColor Green
    Write-Host "Location: $finalOutputFbx" -ForegroundColor Cyan
    Write-Host "File size: $([Math]::Round($finalSizeMB, 2)) MB" -ForegroundColor Cyan
} else {
    Write-Host "WARNING: Final FBX file not found at expected location" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Pipeline Statistics:" -ForegroundColor Cyan
if (-not $SkipTextureConsolidation -and -not $OnlyFinalMerge) {
    Write-Host "  Texture consolidation: $($step05Time.ToString('hh\:mm\:ss'))" -ForegroundColor White
}
if (-not $OnlyFinalMerge -and -not $SkipBatchProcessing) {
    Write-Host "  Batch processing: $($step1Time.ToString('hh\:mm\:ss'))" -ForegroundColor White
}
Write-Host "  Final merge: $($step2Time.ToString('hh\:mm\:ss'))" -ForegroundColor White

if (-not $OnlyFinalMerge -and -not $SkipBatchProcessing) {
    if (-not $SkipTextureConsolidation) {
        $totalTime = $step05Time + $step1Time + $step2Time
    } else {
        $totalTime = $step1Time + $step2Time
    }
    Write-Host "  Total time: $($totalTime.ToString('hh\:mm\:ss'))" -ForegroundColor White
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
