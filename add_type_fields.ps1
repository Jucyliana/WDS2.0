# Script para añadir el campo "Type" a los archivos profiles.json y units.json

# Función para procesar archivos profiles.json
function Add-TypeToProfiles {
    param($filePath)
    
    $content = Get-Content -Path $filePath -Raw -Encoding UTF8
    
    # Verificar si ya tiene el campo "Type"
    if ($content -match '"Type":\s*"Profile"') {
        Write-Host "El archivo ya tiene el campo Type: $filePath" -ForegroundColor Yellow
        return
    }
    
    # Reemplazar el patrón para añadir "Type": "Profile" después de "Name"
    $pattern = '("Name":\s*"[^"]+",)'
    $replacement = '$1' + "`n" + '    "Type": "Profile",'
    
    $newContent = $content -replace $pattern, $replacement
    
    # Guardar el archivo con UTF8 sin BOM
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($filePath, $newContent, $utf8NoBom)
    
    Write-Host "Procesado: $filePath" -ForegroundColor Green
}

# Función para procesar archivos units.json
function Add-TypeToUnits {
    param($filePath)
    
    $content = Get-Content -Path $filePath -Raw -Encoding UTF8
    
    # Verificar si ya tiene el campo "Type"
    if ($content -match '"Type":\s*"Unit"') {
        Write-Host "El archivo ya tiene el campo Type: $filePath" -ForegroundColor Yellow
        return
    }
    
    # Reemplazar el patrón para añadir "Type": "Unit" después de "Name"
    $pattern = '("Name":\s*"[^"]+",)'
    $replacement = '$1' + "`n" + '    "Type": "Unit",'
    
    $newContent = $content -replace $pattern, $replacement
    
    # Guardar el archivo con UTF8 sin BOM
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($filePath, $newContent, $utf8NoBom)
    
    Write-Host "Procesado: $filePath" -ForegroundColor Green
}

# Obtener todos los archivos profiles.json
$profileFiles = Get-ChildItem -Path "C:\DesarrollosUnity\WDS2.0" -Recurse -Filter "profiles.json"
Write-Host "`nProcesando $($profileFiles.Count) archivos profiles.json..." -ForegroundColor Cyan

foreach ($file in $profileFiles) {
    Add-TypeToProfiles -filePath $file.FullName
}

# Obtener todos los archivos units.json
$unitFiles = Get-ChildItem -Path "C:\DesarrollosUnity\WDS2.0" -Recurse -Filter "units.json"
Write-Host "`nProcesando $($unitFiles.Count) archivos units.json..." -ForegroundColor Cyan

foreach ($file in $unitFiles) {
    Add-TypeToUnits -filePath $file.FullName
}

Write-Host "`n¡Proceso completado!" -ForegroundColor Green
Write-Host "Total de archivos procesados: $($profileFiles.Count + $unitFiles.Count)" -ForegroundColor Green
