from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


WorkSuitability = Tuple[str, str, int]


@dataclass
class Pal:
    id: str
    name: str
    elements: List[Dict[str, str]]
    work_suitability: List[WorkSuitability]
    hp: str
    attack: str
    defense: str
    alpha_title: Optional[str] = None
    image: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "id": self.id,
            "element": self.elements,
            "suitability": [
                {
                    "id": ws_id,
                    "name": ws_name,
                    "level": level,
                }
                for (ws_id, ws_name, level) in self.work_suitability
            ],
            "alphaTitle": self.alpha_title,
            "image": self.image,
            "stats": {
                "hp": self.hp,
                "attack": self.attack,
                "defense": self.defense,
            },
        }
