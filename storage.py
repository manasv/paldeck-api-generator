import json
from models import Pal
import os

def save_to_json(pals: list, filename: str = "pals.json"):
    """Save base Pal data to combined JSON file"""
    output_path = os.path.join("output", filename)
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump([pal.to_dict() for pal in pals], f, indent=2)

def save_individual_pal(pal_data: dict, output_dir: str = "pals"):
    """Save individual Pal data with details"""
    output_dir = os.path.join("output", output_dir)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f"{pal_data['id']}.json")
    with open(filename, 'w') as f:
        json.dump(pal_data, f, indent=2)