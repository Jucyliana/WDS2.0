import json
import os
from pathlib import Path

def categorize_statline(statline):
    """Categorize a statline based on its attributes."""
    attributes = statline.get("Attributes", {})
    
    # Check for Ad/Ma (movement)
    if "Ad" in attributes and "Ma" in attributes:
        return 1
    # Check for HP/Df (defensive)
    elif "HP" in attributes and "Df" in attributes:
        return 2
    # Check for At/Of (offensive)
    elif "At" in attributes and "Of" in attributes:
        return 3
    else:
        # Unknown category, keep at end
        return 4

def reorder_profile_children(profile, statline_categories):
    """Reorder the children of a profile based on statline categories."""
    if "Children" not in profile or not profile["Children"]:
        return profile
    
    # Get children with their categories
    children_with_categories = []
    for child in profile["Children"]:
        child_id = child.get("Id", "")
        category = statline_categories.get(child_id, 4)
        children_with_categories.append((category, child))
    
    # Sort by category
    children_with_categories.sort(key=lambda x: x[0])
    
    # Update profile with sorted children
    profile["Children"] = [child for _, child in children_with_categories]
    
    return profile

def process_faction(faction_path):
    """Process profiles in a faction folder."""
    statlines_path = faction_path / "statlines.json"
    profiles_path = faction_path / "profiles.json"
    
    if not statlines_path.exists() or not profiles_path.exists():
        print(f"Skipping {faction_path.name} - missing files")
        return
    
    # Load statlines and categorize them
    with open(statlines_path, 'r', encoding='utf-8') as f:
        statlines = json.load(f)
    
    statline_categories = {}
    for statline in statlines:
        statline_id = statline.get("Id", "")
        category = categorize_statline(statline)
        statline_categories[statline_id] = category
    
    # Load profiles
    with open(profiles_path, 'r', encoding='utf-8') as f:
        profiles = json.load(f)
    
    # Reorder children in each profile
    modified = False
    for profile in profiles:
        old_children = profile.get("Children", []).copy() if "Children" in profile else []
        profile = reorder_profile_children(profile, statline_categories)
        new_children = profile.get("Children", [])
        if old_children != new_children:
            modified = True
    
    # Save updated profiles
    if modified:
        with open(profiles_path, 'w', encoding='utf-8') as f:
            json.dump(profiles, f, indent=2, ensure_ascii=False)
        print(f"Updated {faction_path.name}")
    else:
        print(f"No changes needed for {faction_path.name}")

def main():
    """Process all 9th age factions."""
    base_path = Path(r"c:\DesarrollosUnity\WDS2.0\9th age")
    
    if not base_path.exists():
        print(f"Path not found: {base_path}")
        return
    
    # Process each faction folder
    for faction_dir in base_path.iterdir():
        if faction_dir.is_dir():
            process_faction(faction_dir)

if __name__ == "__main__":
    main()
