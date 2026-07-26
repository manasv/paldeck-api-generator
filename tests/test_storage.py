import json

from models import Pal
from storage import save_individual_pal, save_to_json


def test_storage_writes_utf8_json_atomically(tmp_path):
    pal = Pal(
        id="001",
        name="Pál",
        elements=[],
        work_suitability=[],
        hp="1",
        attack="2",
        defense="3",
    )

    combined_path = save_to_json([pal], output_dir=tmp_path)
    individual_path = save_individual_pal(
        pal.to_dict(),
        output_dir=tmp_path / "pals",
    )

    assert json.loads(combined_path.read_text(encoding="utf-8"))[0]["name"] == "Pál"
    assert json.loads(individual_path.read_text(encoding="utf-8"))["id"] == "001"
    assert not list(tmp_path.rglob("*.tmp"))
