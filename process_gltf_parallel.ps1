# Parallel GLTF to FBX Batch Processor with Optimization
param(
    [string]$ConfigPath = "config.json",
    [int]$FilesPerBatch = 10,
    [float]$DecimateRatio = 0.5
)

# Load configuration
$config = Get-Content $ConfigPath | ConvertFrom-Json

$projectRoot = $config.paths.projectRoot
$blenderExe = $config.paths.blenderExecutable
$modelLibDir = Join-Path $projectRoot $config.folders.modelLib
$textureDir = Join-Path $projectRoot $config.folders.modelLibTextures
$batchOutputDir = Join-Path $projectRoot "gltf_export\batch_fbx"
$maxParallel = $config.processing.maxParallelBlenderInstances

$scriptPath = Join-Path $projectRoot "merge_gltf_batch_optimized.py"

# Create batch output directory
if (-not (Test-Path $batchOutputDir)) {
    New-Item -ItemType Directory -Path $batchOutputDir | Out-Null
}

# Get all GLTF files
$gltfFiles = Get-ChildItem -Path $modelLibDir -Filter "*_LOD00.gltf" | Sort-Object Name

if ($gltfFiles.Count -eq 0) {
    Write-Host "No GLTF files found in $modelLibDir" -ForegroundColor Red
    exit 1
}

Write-Host "Found $($gltfFiles.Count) GLTF files" -ForegroundColor Cyan
Write-Host "Files per batch: $FilesPerBatch" -ForegroundColor Cyan
Write-Host "Decimate ratio: $DecimateRatio" -ForegroundColor Cyan
Write-Host "Max parallel instances: $maxParallel" -ForegroundColor Cyan

# Split files into batches
$batches = @()
for ($i = 0; $i -lt $gltfFiles.Count; $i += $FilesPerBatch) {
    $batchFiles = $gltfFiles[$i..[Math]::Min($i + $FilesPerBatch - 1, $gltfFiles.Count - 1)]
    $batches += ,@($batchFiles)
}

Write-Host "Created $($batches.Count) batches" -ForegroundColor Cyan
Write-Host ""

# Process batches in parallel
$jobs = @()
$completed = 0
$failed = 0
$startTime = Get-Date

for ($batchIdx = 0; $batchIdx -lt $batches.Count; $batchIdx++) {
    # Wait if we've hit the parallel limit
    while ($jobs.Count -ge $maxParallel) {
        $jobs = $jobs | Where-Object { -not $_.HasExited }
        Start-Sleep -Milliseconds $config.processing.processCheckIntervalMs
    }
    
    $batch = $batches[$batchIdx]
    $batchNum = $batchIdx + 1
    $outputFbx = Join-Path $batchOutputDir "batch_$($batchNum.ToString('D4')).fbx"
    
    # Create pipe-separated list of GLTF paths
    $gltfPaths = ($batch | ForEach-Object { $_.FullName }) -join "|"
    
    Write-Host "[$batchNum/$($batches.Count)] Starting batch with $($batch.Count) files..." -ForegroundColor Yellow
    
    # Build Blender command
    $blenderArgs = @(
        "--background",
        "--python", $scriptPath,
        "--",
        $gltfPaths,
        $textureDir,
        $outputFbx,
        $DecimateRatio
    )
    
    # Start Blender process
    $process = Start-Process -FilePath $blenderExe `
                            -ArgumentList $blenderArgs `
                            -NoNewWindow `
                            -PassThru `
                            -RedirectStandardOutput (Join-Path $batchOutputDir "batch_$($batchNum.ToString('D4')).log") `
                            -RedirectStandardError (Join-Path $batchOutputDir "batch_$($batchNum.ToString('D4')).err")
    
    $jobs += $process
}

# Wait for all jobs to complete
Write-Host ""
Write-Host "Waiting for all batches to complete..." -ForegroundColor Cyan

while ($jobs.Count -gt 0) {
    $jobs = $jobs | Where-Object { -not $_.HasExited }
    
    $runningCount = $jobs.Count
    $completedCount = $batches.Count - $runningCount
    
    $elapsed = (Get-Date) - $startTime
    $progress = [Math]::Round(($completedCount / $batches.Count) * 100, 1)
    
    Write-Host "`r[$completedCount/$($batches.Count)] ($progress%) Running: $runningCount | Elapsed: $($elapsed.ToString('hh\:mm\:ss'))" -NoNewline -ForegroundColor Green
    
    Start-Sleep -Milliseconds $config.processing.processCheckIntervalMs
}

Write-Host ""
Write-Host ""

# Check results
$outputFiles = Get-ChildItem -Path $batchOutputDir -Filter "batch_*.fbx"
$completed = $outputFiles.Count
$failed = $batches.Count - $completed

$totalTime = (Get-Date) - $startTime

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Batch Processing Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Total batches: $($batches.Count)" -ForegroundColor White
Write-Host "Completed: $completed" -ForegroundColor Green
Write-Host "Failed: $failed" -ForegroundColor $(if ($failed -gt 0) { "Red" } else { "Green" })
Write-Host "Total time: $($totalTime.ToString('hh\:mm\:ss'))" -ForegroundColor White
Write-Host "Output directory: $batchOutputDir" -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Cyan

if ($failed -gt 0) {
    Write-Host ""
    Write-Host "Check log files in $batchOutputDir for error details" -ForegroundColor Yellow
}
