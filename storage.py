import json
from pathlib import Path
from typing import Iterable, Union

from models import Pal


PathLike = Union[str, Path]


def _write_json(data: object, path: Path) -> None:
    """Write JSON atomically so interrupted runs do not leave corrupt files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    with temporary_path.open("w", encoding="utf-8") as output_file:
        json.dump(data, output_file, indent=2, ensure_ascii=False)
        output_file.write("\n")
    temporary_path.replace(path)


def save_to_json(
    pals: Iterable[Union[Pal, dict]],
    filename: str = "pals.json",
    output_dir: PathLike = "output",
) -> Path:
    """Save Pal data to a combined JSON file."""
    output_path = Path(output_dir) / filename
    serialized_pals = [
        pal.to_dict() if isinstance(pal, Pal) else pal
        for pal in pals
    ]
    _write_json(serialized_pals, output_path)
    return output_path


def save_individual_pal(
    pal_data: dict,
    output_dir: PathLike = "output/pals",
) -> Path:
    """Save one complete Pal record."""
    output_path = Path(output_dir) / f"{pal_data['id']}.json"
    _write_json(pal_data, output_path)
    return output_path
