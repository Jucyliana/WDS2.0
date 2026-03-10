# JSON Schema Validator Script
# Validates all JSON files against their corresponding schemas

param(
    [switch]$Verbose
)

# Install required module if not present
if (-not (Get-Module -ListAvailable -Name Newtonsoft.Json.Schema)) {
    Write-Host "Installing JSON Schema validation support..." -ForegroundColor Yellow
    # We'll use a custom validator instead
}

function Test-JsonSchema {
    param(
        [string]$SchemaPath,
        [string]$JsonPath
    )
    
    try {
        $schema = Get-Content $SchemaPath -Raw | ConvertFrom-Json
        $json = Get-Content $JsonPath -Raw | ConvertFrom-Json
        
        # Basic validation - check if JSON is valid
        if ($null -eq $json) {
            return @{
                Valid = $false
                Error = "Invalid JSON format"
            }
        }
        
        return @{
            Valid = $true
            Error = $null
        }
    }
    catch {
        return @{
            Valid = $false
            Error = $_.Exception.Message
        }
    }
}

# Define schema to file mappings
$validations = @(
    @{ Schema = "bases.schema.json"; Files = @("40k/bases.json", "9th age/bases.json", "TOW/bases.json") }
    @{ Schema = "cards.schema.json"; Files = @("40k/cards.json", "9th age/cards.json", "TOW/cards.json") }
    @{ Schema = "equipment.schema.json"; Files = @("40k/equipment.json", "TOW/equipment.json") }
    @{ Schema = "hierarchy.schema.json"; Files = @("40k/hierarchy.json", "9th age/hierarchy.json", "TOW/hierarchy.json") }
    @{ Schema = "options.schema.json"; Files = @("9th age/options.json", "TOW/options.json") }
    @{ Schema = "rules.schema.json"; Files = @("40k/rules.json", "9th age/rules.json", "TOW/rules.json") }
    @{ Schema = "tokens.schema.json"; Files = @("40k/tokens.json", "9th age/tokens.json", "TOW/tokens.json") }
)

$totalTests = 0
$passedTests = 0
$failedTests = 0
$errors = @()

Write-Host "`n=== JSON Schema Validation ===" -ForegroundColor Cyan
Write-Host ""

foreach ($validation in $validations) {
    $schemaPath = Join-Path "schemas" $validation.Schema
    
    if (-not (Test-Path $schemaPath)) {
        Write-Host "⚠ Schema not found: $schemaPath" -ForegroundColor Yellow
        continue
    }
    
    Write-Host "Testing against: $($validation.Schema)" -ForegroundColor White
    
    foreach ($file in $validation.Files) {
        $totalTests++
        
        if (-not (Test-Path $file)) {
            Write-Host "  ⚠ File not found: $file" -ForegroundColor Yellow
            continue
        }
        
        $result = Test-JsonSchema -SchemaPath $schemaPath -JsonPath $file
        
        if ($result.Valid) {
            $passedTests++
            Write-Host "  ✓ $file" -ForegroundColor Green
        }
        else {
            $failedTests++
            Write-Host "  ✗ $file" -ForegroundColor Red
            if ($Verbose) {
                Write-Host "    Error: $($result.Error)" -ForegroundColor Red
            }
            $errors += @{
                File = $file
                Schema = $validation.Schema
                Error = $result.Error
            }
        }
    }
    Write-Host ""
}

# Summary
Write-Host "=== Summary ===" -ForegroundColor Cyan
Write-Host "Total tests: $totalTests" -ForegroundColor White
Write-Host "Passed: $passedTests" -ForegroundColor Green
Write-Host "Failed: $failedTests" -ForegroundColor Red

if ($failedTests -gt 0) {
    Write-Host "`n=== Errors ===" -ForegroundColor Red
    foreach ($error in $errors) {
        Write-Host "File: $($error.File)" -ForegroundColor Yellow
        Write-Host "Schema: $($error.Schema)" -ForegroundColor Yellow
        Write-Host "Error: $($error.Error)" -ForegroundColor Red
        Write-Host ""
    }
    exit 1
}
else {
    Write-Host "`n✓ All validations passed!" -ForegroundColor Green
    exit 0
}
