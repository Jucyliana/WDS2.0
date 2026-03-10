#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para convertir Children e ItemsToAdd de objetos a arrays
Formato antiguo: "Children": {"id1": "value1", "id2": "value2"}
Formato nuevo: "Children": [{"Id": "id1", "Info": "value1"}, {"Id": "id2", "Info": "value2"}]
"""

import json
import os
from pathlib import Path

def convert_children_to_array(obj):
    """Convierte recursivamente Children e ItemsToAdd de objeto a array."""
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            if key in ["Children", "ItemsToAdd"] and isinstance(value, dict):
                # Convertir de objeto a array
                array_items = []
                for k, v in value.items():
                    if v == "":
                        # Si el valor es cadena vacía, omitir "Info"
                        array_items.append({"Id": k})
                    else:
                        # Valor no vacío, incluir "Info"
                        array_items.append({"Id": k, "Info": v})
                result[key] = array_items
            elif key in ["ReferencedItemsToAdd", "ReferencedItemsToRemove"] and isinstance(value, dict):
                # Convertir de objeto a array
                # Si el valor es un objeto anidado, usar "Ref", si es string usar "Info"
                array_items = []
                for k, v in value.items():
                    if isinstance(v, dict):
                        array_items.append({"Id": k, "Ref": v})
                    elif v == "":
                        # Si el valor es cadena vacía, omitir "Info"
                        array_items.append({"Id": k})
                    else:
                        array_items.append({"Id": k, "Info": v})
                result[key] = array_items
            else:
                # Procesar recursivamente
                result[key] = convert_children_to_array(value)
        return result
    elif isinstance(obj, list):
        return [convert_children_to_array(item) for item in obj]
    else:
        return obj

def process_file(file_path):
    """Procesa un archivo JSON individual."""
    try:
        # Intentar leer con utf-8-sig primero (maneja BOM), luego utf-8
        content = None
        for encoding in ['utf-8-sig', 'utf-8']:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except:
                continue
        
        if content is None:
            return 'error', 'No se pudo leer el archivo'
        
        # Verificar si necesita conversión
        if '"Children"' not in content and '"ItemsToAdd"' not in content and '"ReferencedItemsToAdd"' not in content and '"ReferencedItemsToRemove"' not in content:
            return 'skip', None
        
        # Parsear JSON
        data = json.loads(content)
        
        # Convertir
        converted = convert_children_to_array(data)
        
        # Guardar con formato bonito (sin BOM)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(converted, f, indent=2, ensure_ascii=False)
        
        return 'success', None
    except Exception as e:
        return 'error', str(e)

def main():
    script_dir = Path(__file__).parent
    folders = ["40k", "9th age", "TOW", "TOW_OLD", "WAP"]
    file_types = ["profiles.json", "statlines.json", "options.json", "units.json", "equipment.json", "modifiedprofile.json", "modifiedunit.json"]
    
    total_files = 0
    processed_files = 0
    skipped_files = 0
    error_files = []
    
    for folder in folders:
        folder_path = script_dir / folder
        if not folder_path.exists():
            continue
        
        print(f"\nProcesando carpeta: {folder}")
        
        for file_type in file_types:
            files = list(folder_path.rglob(file_type))
            
            for file_path in files:
                total_files += 1
                rel_path = file_path.relative_to(script_dir)
                
                status, error = process_file(file_path)
                
                if status == 'success':
                    processed_files += 1
                    print(f"  ✓ {rel_path}")
                elif status == 'skip':
                    skipped_files += 1
                    print(f"  - {rel_path} (sin cambios necesarios)")
                else:
                    error_files.append((str(rel_path), error))
                    print(f"  ✗ {rel_path}: {error}")
    
    print("\n" + "="*60)
    print("Resumen:")
    print(f"  Total de archivos revisados: {total_files}")
    print(f"  Archivos convertidos: {processed_files}")
    print(f"  Archivos sin cambios: {skipped_files}")
    print(f"  Archivos con errores: {len(error_files)}")
    
    if error_files:
        print("\nArchivos con errores:")
        for file, error in error_files:
            print(f"  - {file}: {error}")
    
    print("\nConversion completada!")

if __name__ == "__main__":
    main()
