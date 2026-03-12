import json
import os
from pathlib import Path

# Attribute mapping
ATTRIBUTE_MAPPING = {
    "Ad": "Cha",
    "Ma": "Mob",
    "Di": "Dis",
    "Df": "Def",
    "Re": "Res",
    "At": "Att",
    "Of": "Off",
    "St": "Str",
    "Ag": "Agi"
}

def rename_statline_attributes(statline):
    """Rename attributes in a statline based on the mapping."""
    if "Attributes" not in statline:
        return statline
    
    new_attributes = {}
    for old_key, value in statline["Attributes"].items():
        new_key = ATTRIBUTE_MAPPING.get(old_key, old_key)
        new_attributes[new_key] = value
    
    statline["Attributes"] = new_attributes
    return statline

def process_faction(faction_path):
    """Process statlines in a faction folder."""
    statlines_path = faction_path / "statlines.json"
    
    if not statlines_path.exists():
        print(f"Skipping {faction_path.name} - missing statlines.json")
        return
    
    # Load statlines
    with open(statlines_path, 'r', encoding='utf-8') as f:
        statlines = json.load(f)
    
    # Rename attributes in each statline
    modified = False
    for statline in statlines:
        old_attributes = statline.get("Attributes", {}).copy() if "Attributes" in statline else {}
        statline = rename_statline_attributes(statline)
        new_attributes = statline.get("Attributes", {})
        if old_attributes != new_attributes:
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
