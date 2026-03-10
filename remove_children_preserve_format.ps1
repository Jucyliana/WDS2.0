# Script to remove Children field from all statlines in 40k folders
# This version preserves the original JSON formatting

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
        # Read the file as text
        $content = Get-Content -Path $file.FullName -Raw -Encoding UTF8
        $originalContent = $content
        
        # Remove Children blocks using regex
        # Pattern matches: ,\n  "Children": [...] or ,\n    "Children": [...]
        # Handles both single line and multiline Children arrays
        $pattern = ',\s*[\r\n]+\s+"Children":\s*\[(?:[^\[\]]|\[(?:[^\[\]]|\[[^\]]*\])*\])*\]'
        $content = $content -replace $pattern, ''
        
        if ($content -ne $originalContent) {
            # Save the modified content back to file
            [System.IO.File]::WriteAllText($file.FullName, $content, [System.Text.UTF8Encoding]::new($false))
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
