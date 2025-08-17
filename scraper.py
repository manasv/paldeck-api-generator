from bs4 import BeautifulSoup
from models import Pal
from utils import smart_capitalize, find_pal_image_url
import requests
import re
from pathlib import Path

# Work suitability map
WORK_SUITABILITY_MAP = [
    (0, "kindling", "Kindling"),
    (1, "watering", "Watering"),
    (2, "planting", "Planting"),
    (3, "generating_electricity", "Generating Electricity"),
    (4, "handiwork", "Handiwork"),
    (5, "gathering", "Gathering"),
    (6, "lumbering", "Lumbering"),
    (7, "mining", "Mining"),
    (8, "medicine_production", "Medicine Production"),
    (9, "cooling", "Cooling"),
    (10, "transporting", "Transporting"),
    (11, "farming", "Farming"),
]


def scrape_pals():
    resources_url = "https://paldeck.pages.dev/images/pals"
    url = "https://palworld.wiki.gg/wiki/Pals"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    pals = []
    table = soup.find("table", {"class": "wikitable"})

    for row in table.find_all("tr")[1:]:
        cols = row.find_all("td")
        if len(cols) < 19:  # Verify 19 columns (0-18)
            continue

        name = cols[0].text.strip()
        pal_id = cols[1].text.strip()
        elements = [
            {"name": a.text.strip(), "id": a.text.strip().lower()}
            for a in cols[2].find_all("a")
        ]

        # Stats
        hp = cols[3].text.strip()
        attack = cols[4].text.strip()
        defense = cols[5].text.strip()

        # Work suitability - columns 6-17 (12 columns)
        work_suitability = []
        for i in range(6, 18):
            level = cols[i].text.strip()
            if level.isdigit():
                _, ws_id, ws_name = WORK_SUITABILITY_MAP[i - 6]
                work_suitability.append((ws_id, ws_name, int(level)))

        # Alpha title from column 18
        alpha_title = cols[18].text.strip() or None

        pals.append(
            Pal(
                pal_id=pal_id,
                name=name,
                elements=elements,
                work_suitability=work_suitability,
                hp=hp,
                attack=attack,
                defense=defense,
                alpha_title=alpha_title,
                image=f"{resources_url}/{pal_id}",
            )
        )

    return pals


def scrape_pal_details(pal_name: str) -> dict:
    """Scrape detailed information from a Pal's individual page"""
    base_url = "https://palworld.wiki.gg/wiki/"
    sanitized_name = pal_name.replace(" ", "_").title()
    url = f"{base_url}{sanitized_name}"

    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")

        return {
            "description": _parse_description(soup),
            "partnerSkill": _parse_partner_skill(soup),
            "activeSkills": _parse_active_skills(soup),
            "possibleDrops": _parse_possible_drops(soup),
            "food": _parse_food_requirement(soup),
        }

    except Exception as e:
        print(f"Error scraping details for {pal_name}: {str(e)}")
        return {}


def _parse_description(soup) -> str:
    """Extract Pal description from Paldeck section"""
    paldeck_section = soup.find("div", {"id": "mw-customcollapsible-paldeck"})
    if not paldeck_section:
        return ""

    for element_type in ["i", "p", "div"]:
        desc_element = paldeck_section.find(element_type)
        if desc_element and desc_element.text.strip():
            return desc_element.text.strip()

    return ""


def _parse_partner_skill(soup) -> dict:
    """Extract partner skill information"""
    skill_name_div = soup.find("div", {"data-source": "partnerskill"})
    skill_desc_div = soup.find("div", {"data-source": "partnerskill_desc"})

    if not skill_name_div or not skill_desc_div:
        return {}

    return {
        "name": skill_name_div.find("div", class_="pi-data-value").text.strip(),
        "description": skill_desc_div.find("div", class_="pi-data-value").text.strip(),
        "id": skill_name_div.find("div", class_="pi-data-value")
        .text.strip()
        .lower()
        .replace(" ", "_"),
    }


def _parse_active_skills(soup) -> list:
    """Extract active skills at different levels"""
    active_skills = []
    skill_levels = [1, 7, 15, 22, 30, 40, 50]

    for level in skill_levels:
        skill_div = soup.find("div", {"data-source": f"activeskill{level}"})
        if not skill_div:
            continue

        skill_name = skill_div.find("div", class_="pi-data-value").text.strip()
        if "???" in skill_name:
            continue

        active_skills.append(
            {
                "name": skill_name,
                "level": level,
                "id": skill_name.lower().replace(" ", "_"),
            }
        )

    return active_skills


def _parse_possible_drops(soup) -> list:
    """Extract possible drops from regular and alpha sections"""
    drops_container = soup.find("div", {"data-ref": "3"})
    if not drops_container:
        return []

    return [
        *_parse_drop_section(drops_container, "drop", "regular"),
        *_parse_drop_section(drops_container, "alphadrop", "alpha"),
    ]


def _parse_drop_section(container, prefix: str, drop_type: str) -> list:
    """Parse a single drop section (regular or alpha)"""
    drops = []
    drop_divs = container.find_all(
        "div", {"data-source": lambda x: x and x.startswith(prefix)}
    )

    for div in drop_divs:
        drop_text = div.find("div", class_="pi-data-value").text.strip()

        # Skip entries with unknown data
        if "???" in drop_text:
            continue

        # Clean up non-breaking spaces and whitespace
        clean_text = drop_text.replace("\u00a0", " ").replace("  ", " ")

        # Split into main part and rate part
        match = re.match(r"^(.*?)\s*\((.*?)\)$", clean_text)
        if match:
            main_part, rate_part = match.groups()
        else:
            main_part = clean_text
            rate_part = ""

        # Extract amount and name
        amount_match = re.match(r"^(\d+[\-–]\d+|\d+)\s+(.*)", main_part)
        if amount_match:
            amount = amount_match.group(1).replace("–", "-")
            name = amount_match.group(2).strip()
        else:
            # Handle items without specified quantity
            amount = "1"
            name = main_part.strip()

        # Skip if name is still empty after parsing
        if not name:
            continue

        # Parse drop rate
        drop_rate = 100  # default
        if "%" in rate_part:
            rate_match = re.search(r"(\d+)%", rate_part)
            if rate_match:
                drop_rate = int(rate_match.group(1))

        drops.append(
            {
                "name": name,
                "id": name.lower().replace(" ", "_"),
                "amount": amount,
                "dropRate": drop_rate,
                "dropType": drop_type,
            }
        )

    return drops


def _parse_food_requirement(soup) -> int:
    """Parse the number of food icons required"""
    food_container = soup.find("span", class_="foodicons")
    if not food_container:
        return 0

    # Count active food icons by image filename
    active_icons = food_container.find_all("img", src=lambda x: x and "Food_On" in x)
    return len(active_icons)


def download_pal_image(pal_name: str, pal_id: str) -> str:
    """Download pal image and return path"""

    formatted_name = "_".join(smart_capitalize(word) for word in pal_name.split(" "))
    page_url = f"https://palworld.wiki.gg/wiki/{formatted_name}"
    image_path = f"images/pals/{pal_id}.png"

    Path(image_path).parent.mkdir(parents=True, exist_ok=True)

    try:
        page_response = requests.get(page_url, timeout=10)
        if page_response.status_code != 200:
            print(f"Failed to fetch page for {pal_name} from {page_url}")
            return None

        soup = BeautifulSoup(page_response.content, "html.parser")
        image_url = find_pal_image_url(soup)
        if not image_url:
            print(f"[ERROR] Could not find any suitable image for {pal_name}")
            return None
        if image_url.startswith("/"):
            image_url = "https://palworld.wiki.gg" + image_url

        img_response = requests.get(image_url, stream=True, timeout=10)
        if img_response.status_code == 200 and "image" in img_response.headers.get("Content-Type", ""):
            with open(image_path, "wb") as f:
                for chunk in img_response.iter_content(1024):
                    f.write(chunk)
            return image_path
        else:
            print(f"[ERROR] Failed to download image for {pal_name} from {image_url}")
    except Exception as e:
        print(f"[ERROR] Image download failed for {pal_name}: {str(e)}")
    return None
