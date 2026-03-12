import json
import os
from pathlib import Path

def should_clear_name(statline):
    """Check if a statline should have its name cleared."""
    if "Attributes" not in statline:
        return False
    
    attributes = statline["Attributes"]
    
    # Check if the statline has "Cha" or "HP" as attributes
    if "Cha" in attributes or "HP" in attributes:
        return True
    
    return False

def process_faction(faction_path):
    """Process statlines in a faction folder."""
    statlines_path = faction_path / "statlines.json"
    
    if not statlines_path.exists():
        print(f"Skipping {faction_path.name} - missing statlines.json")
        return
    
    # Load statlines
    with open(statlines_path, 'r', encoding='utf-8') as f:
        statlines = json.load(f)
    
    # Clear names for statlines with Cha or HP attributes
    modified = False
    for statline in statlines:
        if should_clear_name(statline):
            if statline.get("Name", "") != "":
                statline["Name"] = ""
                modified = True
    
    # Save updated statlines
    if modified:
        with open(statlines_path, 'w', encoding='utf-8') as f:
            json.dump(statlines, f, indent=2, ensure_ascii=False)
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
