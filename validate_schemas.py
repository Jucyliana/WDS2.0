#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSON Schema Validator
Validates all JSON files against their corresponding schemas using jsonschema library.
"""

import json
import sys
import io
from pathlib import Path
from typing import Dict, List, Tuple

# Ensure proper UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

try:
    from jsonschema import validate, ValidationError, SchemaError
    from jsonschema.validators import Draft7Validator
except ImportError:
    print("Error: jsonschema library not found.")
    print("Install it with: pip install jsonschema")
    sys.exit(1)


def find_all_files_with_name(root_dir: Path, filename: str) -> List[str]:
    """Find all files with a specific name in subdirectories."""
    files = []
    for path in root_dir.rglob(filename):
        # Get relative path from root
        rel_path = path.relative_to(root_dir)
        files.append(str(rel_path).replace('\\', '/'))
    return sorted(files)


# Define schema to file mappings
# For files in root game directories
VALIDATIONS = [
    {
        "schema": "schemas/bases.schema.json",
        "files": ["40k/bases.json", "9th age/bases.json", "TOW/bases.json"]
    },
    {
        "schema": "schemas/cards.schema.json",
        "files": ["40k/cards.json", "9th age/cards.json", "TOW/cards.json"]
    },
    {
        "schema": "schemas/equipment.schema.json",
        "files": ["40k/equipment.json", "TOW/equipment.json"]
    },
    {
        "schema": "schemas/hierarchy.schema.json",
        "files": ["40k/hierarchy.json", "9th age/hierarchy.json", "TOW/hierarchy.json"]
    },
    {
        "schema": "schemas/options.schema.json",
        "files": ["9th age/options.json", "TOW/options.json"]
    },
    {
        "schema": "schemas/rules.schema.json",
        "files": ["40k/rules.json", "9th age/rules.json", "TOW/rules.json"]
    },
    {
        "schema": "schemas/tokens.schema.json",
        "files": ["40k/tokens.json", "9th age/tokens.json", "TOW/tokens.json"]
    }
]

# Schemas for files in army folders (discovered dynamically)
ARMY_FILE_SCHEMAS = [
    {"schema": "schemas/units.schema.json", "filename": "units.json"},
    {"schema": "schemas/profiles.schema.json", "filename": "profiles.json"},
    {"schema": "schemas/statlines.schema.json", "filename": "statlines.json"},
    {"schema": "schemas/equipment.schema.json", "filename": "equipment.json"},
    {"schema": "schemas/options.schema.json", "filename": "options.json"},
    {"schema": "schemas/modifiedunit.schema.json", "filename": "modifiedunit.json"},
    {"schema": "schemas/modifiedprofile.schema.json", "filename": "modifiedprofile.json"}
]


def validate_json_file(schema_path: Path, json_path: Path) -> Tuple[bool, str]:
    """
    Validate a JSON file against a schema.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Load schema
        with open(schema_path, 'r', encoding='utf-8-sig') as f:
            schema = json.load(f)
        
        # Load JSON data
        with open(json_path, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
        
        # Validate schema itself
        Draft7Validator.check_schema(schema)
        
        # Validate data against schema
        validate(instance=data, schema=schema)
        
        return True, None
        
    except FileNotFoundError as e:
        return False, f"File not found: {e.filename}"
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e.msg} at line {e.lineno}, column {e.colno}"
    except SchemaError as e:
        return False, f"Invalid schema: {e.message}"
    except ValidationError as e:
        return False, f"Validation error: {e.message}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def main():
    """Main validation routine."""
    print("\n=== JSON Schema Validation ===\n")
    
    root_dir = Path.cwd()
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    errors = []
    
    # Validate root-level files
    for validation in VALIDATIONS:
        schema_path = root_dir / validation["schema"]
        
        if not schema_path.exists():
            print(f"⚠ Schema not found: {validation['schema']}")
            continue
        
        print(f"Testing against: {validation['schema']}")
        
        for file_path_str in validation["files"]:
            total_tests += 1
            file_path = root_dir / file_path_str
            
            if not file_path.exists():
                print(f"  ⚠ File not found: {file_path_str}")
                continue
            
            is_valid, error = validate_json_file(schema_path, file_path)
            
            if is_valid:
                passed_tests += 1
                print(f"  ✓ {file_path_str}")
            else:
                failed_tests += 1
                print(f"  ✗ {file_path_str}")
                errors.append({
                    "file": file_path_str,
                    "schema": validation["schema"],
                    "error": error
                })
        
        print()
    
    # Validate army-specific files
    for army_schema in ARMY_FILE_SCHEMAS:
        schema_path = root_dir / army_schema["schema"]
        
        if not schema_path.exists():
            print(f"⚠ Schema not found: {army_schema['schema']}")
            continue
        
        # Find all files with this name
        files = find_all_files_with_name(root_dir, army_schema["filename"])
        
        # Filter out root-level files that are already validated
        # Only include files in subdirectories (army folders)
        army_files = [f for f in files if f.count('/') >= 2]
        
        if not army_files:
            print(f"No army-level {army_schema['filename']} files found")
            continue
        
        print(f"Testing against: {army_schema['schema']}")
        print(f"  Found {len(army_files)} {army_schema['filename']} file(s) in army folders")
        
        for file_path_str in army_files:
            total_tests += 1
            file_path = root_dir / file_path_str
            
            is_valid, error = validate_json_file(schema_path, file_path)
            
            if is_valid:
                passed_tests += 1
                print(f"  ✓ {file_path_str}")
            else:
                failed_tests += 1
                print(f"  ✗ {file_path_str}")
                errors.append({
                    "file": file_path_str,
                    "schema": army_schema["schema"],
                    "error": error
                })
        
        print()
    
    # Summary
    print("=== Summary ===")
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")
    
    if failed_tests > 0:
        print("\n=== Errors ===")
        for error in errors:
            print(f"\nFile: {error['file']}")
            print(f"Schema: {error['schema']}")
            print(f"Error: {error['error']}")
        sys.exit(1)
    else:
        print("\n✓ All validations passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
