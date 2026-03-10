# Script para detectar y eliminar objetos duplicados dentro de cada archivo statlines.json o equipment.json
# Detecta objetos que son iguales excepto por el Id
# Mantiene el primero y elimina los duplicados, reemplazando referencias

param(
    [string]$RootPath = ".",
    [ValidateSet("statlines.json", "equipment.json", "profiles.json")]
    [string]$FileName = "statlines.json",
    [switch]$DryRun
)

function Get-ObjectHash {
    param($Object)
    
    # Crear una copia del objeto sin el Id
    $copy = $Object.PSObject.Copy()
    $copy.PSObject.Properties.Remove("Id")
    
    # Convertir a JSON para comparación
    $json = $copy | ConvertTo-Json -Depth 10 -Compress
    return $json
}

function Find-DuplicatesInFile {
    param([string]$FilePath)
    
    Write-Host "`nAnalizando: $FilePath" -ForegroundColor Cyan
    
    try {
        $content = Get-Content -Path $FilePath -Raw -Encoding UTF8 | ConvertFrom-Json
        
        if (-not $content -or $content.Count -eq 0) {
            Write-Host "  Archivo vacío" -ForegroundColor Gray
            return @()
        }
        
        $hashTable = @{}
        $duplicates = @()
        
        foreach ($item in $content) {
            if (-not $item.Id) {
                continue
            }
            
            $hash = Get-ObjectHash -Object $item
            
            if ($hashTable.ContainsKey($hash)) {
                # Duplicado encontrado
                $duplicates += [PSCustomObject]@{
                    File = $FilePath
                    OriginalId = $hashTable[$hash]
                    DuplicateId = $item.Id
                    Name = $item.Name
                }
                
                Write-Host "  Duplicado:" -ForegroundColor Red
                Write-Host "    Original: $($hashTable[$hash])" -ForegroundColor Yellow
                Write-Host "    Duplicado: $($item.Id)" -ForegroundColor Yellow
                Write-Host "    Nombre: $($item.Name)" -ForegroundColor White
            }
            else {
                $hashTable[$hash] = $item.Id
            }
        }
        
        if ($duplicates.Count -eq 0) {
            Write-Host "  Sin duplicados" -ForegroundColor Green
        }
        
        return $duplicates
    }
    catch {
        Write-Host "  Error: $_" -ForegroundColor Red
        return @()
    }
}

function Remove-DuplicatesFromFile {
    param(
        [string]$FilePath,
        [array]$DuplicateIds
    )
    
    Write-Host "`nEliminando duplicados de: $FilePath" -ForegroundColor Cyan
    
    try {
        $content = Get-Content -Path $FilePath -Raw -Encoding UTF8 | ConvertFrom-Json
        $originalCount = $content.Count
        
        # Filtrar duplicados
        $filtered = @($content | Where-Object { $_.Id -notin $DuplicateIds })
        
        $removedCount = $originalCount - $filtered.Count
        
        if ($removedCount -gt 0) {
            if (-not $DryRun) {
                # Convertir a JSON
                $json = ($filtered | ConvertTo-Json -Depth 10)
                
                # Cambiar indentación de 4 a 2 espacios
                $json = $json -replace '(?m)^    ', '  '
                $json = $json -replace '(?m)^        ', '    '
                $json = $json -replace '(?m)^            ', '      '
                $json = $json -replace '(?m)^                ', '        '
                $json = $json -replace '(?m)^                    ', '          '
                $json = $json -replace '(?m)^                        ', '            '
                
                # Desescapar caracteres Unicode que PowerShell escapa automáticamente
                $json = $json -replace '\\u0027', "'"
                
                [System.IO.File]::WriteAllText($FilePath, $json, [System.Text.Encoding]::UTF8)
                Write-Host "  Eliminados: $removedCount objetos" -ForegroundColor Green
            }
            else {
                Write-Host "  [DRY RUN] Se eliminarían: $removedCount objetos" -ForegroundColor Yellow
            }
        }
    }
    catch {
        Write-Host "  Error: $_" -ForegroundColor Red
    }
}

function Replace-IdsInFile {
    param(
        [string]$FilePath,
        [hashtable]$IdMap
    )
    
    try {
        $content = Get-Content -Path $FilePath -Raw -Encoding UTF8
        $modified = $false
        
        foreach ($duplicateId in $IdMap.Keys) {
            $originalId = $IdMap[$duplicateId]
            # Buscar el ID duplicado como valor exacto entre comillas
            $pattern = [regex]::Escape("`"$duplicateId`"")
            $replacement = "`"$originalId`""
            
            if ($content -match $pattern) {
                $content = $content -replace $pattern, $replacement
                $modified = $true
            }
        }
        
        if ($modified) {
            if (-not $DryRun) {
                [System.IO.File]::WriteAllText($FilePath, $content, [System.Text.Encoding]::UTF8)
                Write-Host "  Referencias actualizadas en: $(Split-Path -Leaf $FilePath)" -ForegroundColor Green
            }
            else {
                Write-Host "  [DRY RUN] Se actualizarían referencias en: $(Split-Path -Leaf $FilePath)" -ForegroundColor Yellow
            }
        }
    }
    catch {
        Write-Host "  Error en ${FilePath}: $_" -ForegroundColor Red
    }
}

function Replace-IdsInDirectory {
    param(
        [string]$Directory,
        [hashtable]$IdMap,
        [string]$FileToExclude
    )
    
    Write-Host "`nReemplazando referencias en: $Directory" -ForegroundColor Cyan
    
    $jsonFiles = Get-ChildItem -Path $Directory -Filter "*.json" -File | Where-Object { $_.Name -ne $FileToExclude }
    
    foreach ($file in $jsonFiles) {
        Replace-IdsInFile -FilePath $file.FullName -IdMap $IdMap
    }
}

# Main
Write-Host "=== Detector y Eliminador de Duplicados en $FileName ===" -ForegroundColor Magenta
Write-Host "Ruta: $RootPath" -ForegroundColor Magenta
if ($DryRun) {
    Write-Host "MODO DRY RUN - No se realizarán cambios" -ForegroundColor Yellow
}
Write-Host ""

$allDuplicates = @()
$files = Get-ChildItem -Path $RootPath -Filter $FileName -Recurse -File

Write-Host "Archivos encontrados: $($files.Count)`n"

foreach ($file in $files) {
    $duplicates = Find-DuplicatesInFile -FilePath $file.FullName
    
    if ($duplicates.Count -gt 0) {
        $allDuplicates += $duplicates
        
        # Crear mapa de IDs a reemplazar (Duplicado -> Original)
        $idMap = @{}
        $duplicateIds = @()
        
        foreach ($dup in $duplicates) {
            $idMap[$dup.DuplicateId] = $dup.OriginalId
            $duplicateIds += $dup.DuplicateId
        }
        
        # Eliminar duplicados del archivo
        Remove-DuplicatesFromFile -FilePath $file.FullName -DuplicateIds $duplicateIds
        
        # Reemplazar referencias en otros archivos del mismo directorio
        $directory = Split-Path -Parent $file.FullName
        Replace-IdsInDirectory -Directory $directory -IdMap $idMap -FileToExclude $FileName
    }
}

Write-Host "`n=== RESUMEN ===" -ForegroundColor Magenta
Write-Host "Total duplicados procesados: $($allDuplicates.Count)" -ForegroundColor $(if ($allDuplicates.Count -gt 0) { "Green" } else { "Gray" })

if ($allDuplicates.Count -gt 0) {
    Write-Host "`nDetalle:" -ForegroundColor Yellow
    $allDuplicates | Format-Table -AutoSize
}
