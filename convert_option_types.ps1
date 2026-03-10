# Script to convert Type field from string enum to integer in all options.json files

# Define the enum mapping
$typeMapping = @{
    "UnitGlobalChange" = 0
    "UnitSwapDisplayable" = 1
    "UnitBasicSwapDisplayable" = 2
    "UnitProfileChange" = 3
    "ModelSwapDisplayable" = 4
    "ModelSwap" = 5
    "ModelAdd" = 6
}

# Find all options.json files
$optionsFiles = Get-ChildItem -Path . -Filter "options.json" -Recurse

Write-Host "Found $($optionsFiles.Count) options.json files"

foreach ($file in $optionsFiles) {
    Write-Host "Processing: $($file.FullName)"
    
    # Read the JSON file
    $content = Get-Content -Path $file.FullName -Raw | ConvertFrom-Json
    
    # Track if any changes were made
    $changed = $false
    
    # Update each option's Type field
    foreach ($option in $content) {
        if ($option.Type -is [string]) {
            $stringType = $option.Type
            if ($typeMapping.ContainsKey($stringType)) {
                $option.Type = $typeMapping[$stringType]
                $changed = $true
                Write-Host "  Updated: $stringType -> $($typeMapping[$stringType])"
            }
        }
    }
    
    # Save the file if changes were made
    if ($changed) {
        $json = $content | ConvertTo-Json -Depth 10
        Set-Content -Path $file.FullName -Value $json
        Write-Host "  Saved: $($file.FullName)" -ForegroundColor Green
    } else {
        Write-Host "  No changes needed" -ForegroundColor Yellow
    }
}

Write-Host "`nConversion complete!"
