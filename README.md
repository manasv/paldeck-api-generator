
# Palworld Wiki Scraper
A web scraping tool to extract Pal data from the Palworld wiki and export it to structured JSON format.

## Features
- Scrapes base Pal information (stats, elements, work suitability)
- Extracts detailed information including skills, drops, and food requirements
- Saves data to:
  - Combined `pals.json` file
  - Individual JSON files per Pal in `/pals` directory
- Error handling and data validation
- Clean data normalization with consistent IDs

## Requirements
- Python 3.9+
- requests
- BeautifulSoup4

## Installation
```bash
git clone [repo-url]
cd palworld-scraper
pip install -r requirements.txt
```

## Usage
```bash
python main.py
```

Sample output:
```
Scraped 137 base Pal records
Saved combined data to pals.json
Processing Kikit (1/137)
...
All individual Pal files saved to pals/ directory
```

## Data Structure
```json
{
  "name": "Kikit",
  "id": "117",
  "element": [{"name": "Ground", "id": "ground"}],
  "suitability": [{"id": "mining", "name": "Mining", "level": 1}],
  "alphaTitle": "Armored to the Teeth",
  "image": "https://.../117",
  "stats": {
    "hp": "75",
    "attack": "70",
    "defense": "90"
  },
  "description": "A decade ago, Kikit soccer was popular...",
  "partnerSkill": {
    "name": "Rollin' Full Oil",
    "description": "While in team...",
    "id": "rollin'_full_oil"
  },
  "activeSkills": [
    {"name": "Power Shot", "level": 1, "id": "power_shot"}
  ],
  "possibleDrops": [
    {"name": "Crude Oil", "amount": "1", "dropRate": 100}
  ],
  "food": 3
}
```

## Notes
- Data is sourced from [Palworld Wiki](https://palworld.wiki.gg/wiki/Pals)
