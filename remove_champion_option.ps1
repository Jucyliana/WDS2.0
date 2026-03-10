# Script to remove Champion option and all its references
$optionId = "2ab96c83-3b3b-4996-8d42-b5cbf11ef692"
$basePath = "c:\DesarrollosUnity\WDS2.0\9th age"

# Function to remove option entries from JSON array
function Remove-OptionFromJson {
    param (
        [string]$filePath,
        [string]$optionId
    )
    
    $content = Get-Content $filePath -Raw | ConvertFrom-Json
    $modified = $false
    
    # Filter out entries with the specified OptionId
    if ($content -is [array]) {
        $original_count = $content.Count
        $content = $content | Where-Object { 
            if ($_.Id -eq $optionId -or $_.OptionId -eq $optionId) {
                $modified = $true
                return $false
            }
            return $true
        }
        
        if ($modified) {
            Write-Host "Removed entries from: $filePath"
            $content | ConvertTo-Json -Depth 10 | Set-Content $filePath -Encoding UTF8
        }
    }
    
    return $modified
}

# Remove from options.json
$optionsFile = Join-Path $basePath "options.json"
Write-Host "Processing options.json..."
Remove-OptionFromJson -filePath $optionsFile -optionId $optionId

# Find and process all modifiedunit.json files
Write-Host "`nProcessing modifiedunit.json files..."
$modifiedUnitFiles = Get-ChildItem -Path $basePath -Recurse -Filter "modifiedunit.json"

$totalFiles = 0
foreach ($file in $modifiedUnitFiles) {
    if (Remove-OptionFromJson -filePath $file.FullName -optionId $optionId) {
        $totalFiles++
    }
}

Write-Host "`nComplete! Modified $totalFiles modifiedunit.json files."
Write-Host "Removed all references to Champion option ($optionId)"
