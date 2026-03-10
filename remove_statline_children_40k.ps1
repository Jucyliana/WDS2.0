# Script to remove Children field from all statlines in 40k folders

$files = Get-ChildItem -Path "40k" -Filter "statlines.json" -Recurse

$totalFiles = $files.Count
$processedFiles = 0
$modifiedFiles = 0

Write-Host "Found $totalFiles statlines.json files in 40k folders"
Write-Host ""

foreach ($file in $files) {
    $processedFiles++
    Write-Host "[$processedFiles/$totalFiles] Processing: $($file.FullName)"
    
    try {
        # Read the JSON file
        $content = Get-Content -Path $file.FullName -Raw -Encoding UTF8
        $statlines = $content | ConvertFrom-Json
        
        $hasChildren = $false
        
        # Remove Children property from each statline
        foreach ($statline in $statlines) {
            if ($statline.PSObject.Properties.Name -contains "Children") {
                $statline.PSObject.Properties.Remove("Children")
                $hasChildren = $true
            }
        }
        
        if ($hasChildren) {
            # Save the modified JSON back to file
            $json = $statlines | ConvertTo-Json -Depth 10 -Compress:$false
            $json | Set-Content -Path $file.FullName -Encoding UTF8 -NoNewline
            Write-Host "  [OK] Removed Children fields" -ForegroundColor Green
            $modifiedFiles++
        } else {
            Write-Host "  [-] No Children fields found" -ForegroundColor Gray
        }
    }
    catch {
        Write-Host "  [ERROR] Error processing file: $_" -ForegroundColor Red
    }
    
    Write-Host ""
}

Write-Host "================================================"
Write-Host "Processing complete!"
Write-Host "Total files processed: $processedFiles"
Write-Host "Files modified: $modifiedFiles"
Write-Host "================================================"
