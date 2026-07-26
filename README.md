# Paldeck API Generator

A Python generator that builds a JSON dataset from the
[Palworld Wiki](https://palworld.wiki.gg/) MediaWiki API.

## Features

- Discovers Pal pages through MediaWiki's template-transclusion API
- Parses structured `Pal`, `Palpedia`, and `Item Drop` wikitext templates
- Fetches page source and image metadata in batches of up to 50
- Downloads each Pal's original wiki icon through the `imageinfo` API
- Normalizes every icon to a transparent 128×128 PNG with Lanczos resampling
- Uses an adaptive 256-color palette and maximum PNG compression to reduce
  generated image weight while retaining transparency
- Writes a complete combined dataset and one JSON file per Pal
- Uses request timeouts, retry handling, atomic JSON writes, and parser
  validation
- Never parses rendered HTML or depends on CSS selectors
- Includes regression tests for API pagination and template variations

## Requirements

- Python 3.9+
- `requests`
- `mwparserfromhell`
- `Pillow`

## Installation

```bash
git clone https://github.com/manasv/paldeck-api-generator.git
cd paldeck-api-generator
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

For development and tests:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Usage

Generate the full dataset:

```bash
python main.py
```

Useful smoke-test options:

```bash
# Process one Pal without downloading its image
python main.py --limit 1 --skip-images

# Write generated files somewhere else
python main.py --output-dir /tmp/paldeck-output
```

Run `python main.py --help` for all options.

## Data pipeline

The generator uses only public MediaWiki API endpoints:

1. `list=embeddedin` lists articles that transclude `Template:Pal`.
2. `prop=revisions` retrieves their raw wikitext in batches.
3. `mwparserfromhell` reads named template parameters into the output schema.
4. Pages without a positive Palpedia number are treated as unreleased.
5. `prop=imageinfo` resolves original icon URLs in batches.

This keeps parsing independent from the wiki's rendered layout and ensures
template changes fail with explicit validation errors instead of silently
producing empty records.

When the wiki source has an explicitly blank value, the generator emits
schema-compatible sentinel data instead of inventing a fact: text uses
`"unknown"`, numeric values use zero, and missing list entries use an object
whose fields contain the same unknown/zero values.

## Output

```text
output/
├── pals.json
├── pals/
│   ├── 001.json
│   └── ...
└── images/
    └── pals/
        ├── 001.png
        └── ...
```

Both `pals.json` and the individual files contain complete records:

```json
{
  "name": "Lamball",
  "id": "001",
  "element": [{"name": "Neutral", "id": "neutral"}],
  "suitability": [
    {"id": "handiwork", "name": "Handiwork", "level": 1}
  ],
  "alphaTitle": "Big Floof",
  "image": "https://paldeck.pages.dev/images/pals/001",
  "stats": {
    "hp": "70",
    "attack": "70",
    "defense": "70"
  },
  "description": "A walk up a hill tends to end with this Pal tumbling back down...",
  "partnerSkill": {
    "name": "Fluffy Shield",
    "description": "When activated, equips to the player and becomes a shield...",
    "id": "fluffy_shield"
  },
  "activeSkills": [
    {"name": "Roly Poly", "level": 1, "id": "roly_poly"}
  ],
  "possibleDrops": [
    {
      "name": "Wool",
      "id": "wool",
      "amount": "1-3",
      "dropRate": 100,
      "dropType": "regular"
    }
  ],
  "food": 1
}
```

## Automation

The GitHub Actions workflow runs the test suite, generates the full output,
and syncs it to the target API repository. It runs on pushes to `main`, on
manual dispatch, and monthly.
