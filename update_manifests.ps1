# Script to update all game manifests with actual files

function Update-Manifest {
    param(
        [string]$GamePath,
        [string]$GameName
    )
    
    Write-Host "Processing $GameName..." -ForegroundColor Cyan
    
    # Get all actual files in the directory
    $actualFiles = Get-ChildItem -Path $GamePath -Recurse -File | 
        ForEach-Object { 
            $relPath = $_.FullName.Substring($GamePath.Length + 1)
            $relPath.Replace("\", "/")
        } | 
        Sort-Object @{Expression={-not $_.Contains("/")}; Descending=$true}, @{Expression={$_}; Ascending=$true}
    
    # Read current manifest
    $manifestPath = Join-Path $GamePath "manifest.json"
    $manifest = Get-Content $manifestPath | ConvertFrom-Json
    
    # Store current version
    $currentVersion = $manifest.version
    
    # Get current files from manifest
    $manifestFiles = $manifest.files
    
    # Find differences
    $missingFiles = $actualFiles | Where-Object { $_ -notin $manifestFiles }
    $notNeededFiles = $manifestFiles | Where-Object { $_ -notin $actualFiles }
    
    # Check if order has changed
    $orderChanged = $false
    if ($manifestFiles.Count -eq $actualFiles.Count) {
        for ($i = 0; $i -lt $actualFiles.Count; $i++) {
            if ($manifestFiles[$i] -ne $actualFiles[$i]) {
                $orderChanged = $true
                break
            }
        }
    }
    
    # Report findings
    Write-Host "  Current files in manifest: $($manifestFiles.Count)" -ForegroundColor Gray
    Write-Host "  Actual files in directory: $($actualFiles.Count)" -ForegroundColor Gray
    
    if ($missingFiles.Count -gt 0) {
        Write-Host "  Missing files to add: $($missingFiles.Count)" -ForegroundColor Yellow
        $missingFiles | ForEach-Object { Write-Host "    + $_" -ForegroundColor Green }
    }
    
    if ($notNeededFiles.Count -gt 0) {
        Write-Host "  Files to remove: $($notNeededFiles.Count)" -ForegroundColor Yellow
        $notNeededFiles | ForEach-Object { Write-Host "    - $_" -ForegroundColor Red }
    }
    
    if ($orderChanged) {
        Write-Host "  Files reordered" -ForegroundColor Yellow
    }
    
    if ($missingFiles.Count -eq 0 -and $notNeededFiles.Count -eq 0 -and -not $orderChanged) {
        Write-Host "  Manifest is up to date!" -ForegroundColor Green
        return
    }
    
    # Update manifest
    $manifest.files = $actualFiles
    $manifest.version = $currentVersion + 1
    
    # Save updated manifest
    $jsonContent = $manifest | ConvertTo-Json -Depth 10
    Set-Content -Path $manifestPath -Value $jsonContent
    
    Write-Host "  Manifest updated! Version: $currentVersion -> $($manifest.version)" -ForegroundColor Green
    Write-Host ""
}

# Process all three games
$workspace = "c:\DesarrollosUnity\WDS2.0"

Update-Manifest -GamePath (Join-Path $workspace "40k") -GameName "Warhammer 40,000"
Update-Manifest -GamePath (Join-Path $workspace "9th age") -GameName "9th Age"
Update-Manifest -GamePath (Join-Path $workspace "TOW") -GameName "The Old World"

Write-Host "All manifests have been updated!" -ForegroundColor Cyan
