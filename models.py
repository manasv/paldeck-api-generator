class Pal:
    def __init__(self, pal_id, name, elements, work_suitability, hp, attack, defense, alpha_title=None, image=None):
        self.id = pal_id
        self.name = name
        self.elements = elements
        self.work_suitability = work_suitability
        self.hp = hp
        self.attack = attack
        self.defense = defense
        self.alpha_title = alpha_title
        self.image = image

    def to_dict(self):
        return {
            "name": self.name,
            "id": self.id,
            "element": self.elements,
            "suitability": [
                {
                    "id": ws_id,
                    "name": ws_name,
                    "level": level
                } for (ws_id, ws_name, level) in self.work_suitability
            ],
            "alphaTitle": self.alpha_title,
            "image": self.image,
            "stats": {
                "hp": self.hp,
                "attack": self.attack,
                "defense": self.defense
            }
        }