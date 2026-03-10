import json
import os
from pathlib import Path

def remove_duplicate_children_from_profiles(folder_path):
    """
    Remove children from profiles that already appear in their referenced statlines.
    """
    profiles_path = os.path.join(folder_path, 'profiles.json')
    statlines_path = os.path.join(folder_path, 'statlines.json')
    
    # Load both files
    with open(profiles_path, 'r', encoding='utf-8') as f:
        profiles = json.load(f)
    
    with open(statlines_path, 'r', encoding='utf-8') as f:
        statlines = json.load(f)
    
    # Create a lookup dictionary for statlines by Id
    statline_lookup = {sl['Id']: sl for sl in statlines}
    
    # Track statistics
    profiles_modified = 0
    total_children_removed = 0
    
    # Process each profile
    for profile in profiles:
        if 'Children' not in profile or not profile['Children']:
            continue
        
        # Find all statline IDs in this profile's children
        statline_ids = [child['Id'] for child in profile['Children'] 
                       if child['Id'].startswith('statline_')]
        
        if not statline_ids:
            continue
        
        # Collect all children from these statlines
        statline_children_ids = set()
        for statline_id in statline_ids:
            if statline_id in statline_lookup:
                statline = statline_lookup[statline_id]
                if 'Children' in statline and statline['Children']:
                    for child in statline['Children']:
                        statline_children_ids.add(child['Id'])
        
        if not statline_children_ids:
            continue
        
        # Remove duplicate children from profile
        original_count = len(profile['Children'])
        profile['Children'] = [
            child for child in profile['Children']
            if child['Id'] not in statline_children_ids or child['Id'].startswith('statline_')
        ]
        
        removed_count = original_count - len(profile['Children'])
        if removed_count > 0:
            profiles_modified += 1
            total_children_removed += removed_count
            print(f"Profile '{profile['Name']}' ({profile['Id']}): removed {removed_count} duplicate children")
    
    # Write back the modified profiles
    with open(profiles_path, 'w', encoding='utf-8') as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)
    
    print(f"\nSummary:")
    print(f"  Profiles modified: {profiles_modified}")
    print(f"  Total children removed: {total_children_removed}")
    print(f"  File saved: {profiles_path}")

# Process TOW folder
tow_folder = r'c:\DesarrollosUnity\WDS2.0\TOW'

# Get all subdirectories in TOW
for item in os.listdir(tow_folder):
    item_path = os.path.join(tow_folder, item)
    if os.path.isdir(item_path):
        profiles_path = os.path.join(item_path, 'profiles.json')
        statlines_path = os.path.join(item_path, 'statlines.json')
        
        if os.path.exists(profiles_path) and os.path.exists(statlines_path):
            print(f"\n{'='*60}")
            print(f"Processing: {item}")
            print(f"{'='*60}")
            remove_duplicate_children_from_profiles(item_path)
