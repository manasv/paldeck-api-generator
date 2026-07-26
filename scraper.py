import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import mwparserfromhell
import requests
from mwparserfromhell.nodes import Template
from PIL import Image, ImageOps, UnidentifiedImageError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from models import Pal
from utils import normalize_pal_id, slugify


API_URL = "https://palworld.wiki.gg/api.php"
IMAGE_RESOURCES_URL = "https://paldeck.pages.dev/images/pals"
REQUEST_TIMEOUT = 20
API_BATCH_SIZE = 50
OUTPUT_IMAGE_SIZE = (128, 128)
OUTPUT_IMAGE_COLORS = 256
UNKNOWN_TEXT = "unknown"
USER_AGENT = (
    "paldeck-api-generator/2.0 "
    "(https://github.com/manasv/paldeck-api-generator)"
)

WORK_SUITABILITY_NAMES = {
    "kindling": ("kindling", "Kindling"),
    "watering": ("watering", "Watering"),
    "planting": ("planting", "Planting"),
    "generating electricity": (
        "generating_electricity",
        "Generating Electricity",
    ),
    "handiwork": ("handiwork", "Handiwork"),
    "gathering": ("gathering", "Gathering"),
    "lumbering": ("lumbering", "Lumbering"),
    "mining": ("mining", "Mining"),
    "medicine production": (
        "medicine_production",
        "Medicine Production",
    ),
    "cooling": ("cooling", "Cooling"),
    "transporting": ("transporting", "Transporting"),
    "farming": ("farming", "Farming"),
}


class ScraperError(RuntimeError):
    """Raised when the wiki API cannot provide valid Pal data."""


def create_session() -> requests.Session:
    """Create an HTTP session with identification and bounded retries."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
    )
    retries = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


def scrape_records(
    session: Optional[requests.Session] = None,
    limit: Optional[int] = None,
) -> List[dict]:
    """Fetch and parse complete records for every released Pal."""
    client = session or create_session()
    if limit is not None and limit < 1:
        raise ValueError("limit must be greater than zero")

    titles = fetch_pal_titles(client)
    pages = fetch_pal_wikitext(titles, client)
    records = []
    for name in titles:
        wikitext = pages[name]
        if not _has_released_pal_id(wikitext):
            continue
        records.append(parse_pal_wikitext(name, None, wikitext))

    records.sort(key=lambda record: _pal_id_sort_key(record["id"]))
    _validate_unique_records(records)
    if limit is not None:
        records = records[:limit]
    if not records:
        raise ScraperError("MediaWiki API returned no released Pals")
    return records


def fetch_pal_titles(
    session: Optional[requests.Session] = None,
) -> List[str]:
    """List every article that directly transcludes Template:Pal."""
    client = session or create_session()
    titles = []
    continuation = {}
    while True:
        payload = _api_get(
            client,
            {
                "action": "query",
                "list": "embeddedin",
                "eititle": "Template:Pal",
                "einamespace": "0",
                "eilimit": "500",
                **continuation,
            },
        )
        titles.extend(
            page["title"]
            for page in payload.get("query", {}).get("embeddedin", [])
            if page.get("title")
        )
        continuation = payload.get("continue", {})
        if not continuation:
            break

    if not titles:
        raise ScraperError(
            "MediaWiki API returned no pages transcluding Template:Pal"
        )
    return list(dict.fromkeys(titles))


def fetch_pal_wikitext(
    pal_names: Sequence[str],
    session: Optional[requests.Session] = None,
) -> Dict[str, str]:
    """Fetch raw wikitext for Pal pages in MediaWiki-sized batches."""
    client = session or create_session()
    pages = {}
    for batch in _batched(pal_names, API_BATCH_SIZE):
        payload = _api_get(
            client,
            {
                "action": "query",
                "titles": "|".join(batch),
                "prop": "revisions",
                "rvprop": "content",
                "rvslots": "main",
            },
        )
        for page in payload.get("query", {}).get("pages", []):
            title = page.get("title", "")
            revisions = page.get("revisions", [])
            if page.get("missing") or not revisions:
                continue
            content = (
                revisions[0]
                .get("slots", {})
                .get("main", {})
                .get("content")
            )
            if title and isinstance(content, str):
                pages[title] = content

    missing = sorted(set(pal_names) - set(pages))
    if missing:
        raise ScraperError(
            "MediaWiki API returned missing Pal pages: " + ", ".join(missing)
        )
    return pages


def fetch_pal_image_urls(
    pal_names: Sequence[str],
    session: Optional[requests.Session] = None,
) -> Dict[str, str]:
    """Resolve original Pal icon URLs through MediaWiki imageinfo."""
    client = session or create_session()
    image_urls = {}
    expected_titles = {
        _normalize_title(f"File:{name} icon.png"): name
        for name in pal_names
    }

    for batch in _batched(pal_names, API_BATCH_SIZE):
        file_titles = [f"File:{name} icon.png" for name in batch]
        payload = _api_get(
            client,
            {
                "action": "query",
                "titles": "|".join(file_titles),
                "prop": "imageinfo",
                "iiprop": "url|mime",
            },
        )
        for page in payload.get("query", {}).get("pages", []):
            name = expected_titles.get(_normalize_title(page.get("title", "")))
            image_info = page.get("imageinfo", [])
            if not name or not image_info:
                continue
            info = image_info[0]
            image_url = info.get("url")
            mime_type = str(info.get("mime", ""))
            if image_url and mime_type.startswith("image/"):
                image_urls[name] = image_url

    missing = sorted(set(pal_names) - set(image_urls))
    if missing:
        raise ScraperError(
            "MediaWiki API returned missing Pal icons: " + ", ".join(missing)
        )
    return image_urls


def parse_pal_wikitext(
    pal_name: str,
    expected_id: Optional[str],
    wikitext: str,
) -> dict:
    """Convert structured Pal page templates to the public JSON schema."""
    wikicode = mwparserfromhell.parse(wikitext)
    pal_template = _find_template(wikicode.filter_templates(), "Pal")
    if pal_template is None:
        raise ScraperError(f"{pal_name} has no Pal template")

    pal_id = normalize_pal_id(_parameter(pal_template, "no"))
    if not pal_id:
        raise ScraperError(f"{pal_name} has no Palpedia ID")
    if expected_id is not None and pal_id != expected_id:
        raise ScraperError(
            f"{pal_name} ID mismatch: expected {expected_id}, "
            f"page template has {pal_id}"
        )

    elements = []
    for parameter_name in ("ele1", "ele2"):
        element_name = _clean_wikitext(_parameter(pal_template, parameter_name))
        if element_name:
            elements.append(
                {"name": element_name, "id": slugify(element_name)}
            )
    if not elements:
        elements.append({"name": UNKNOWN_TEXT, "id": UNKNOWN_TEXT})
    elements.sort(key=lambda element: element["name"])

    work_suitability = _parse_work_suitability(
        _parameter(pal_template, "work_suitability"),
        pal_name,
    )
    if not work_suitability:
        work_suitability.append((UNKNOWN_TEXT, UNKNOWN_TEXT, 0))

    pal = Pal(
        id=pal_id,
        name=pal_name,
        elements=elements,
        work_suitability=work_suitability,
        hp=_parameter(pal_template, "hp") or "0",
        attack=_parameter(pal_template, "attack") or "0",
        defense=_parameter(pal_template, "defense") or "0",
        alpha_title=_optional_clean_parameter(
            pal_template,
            "alpha_title",
        )
        or UNKNOWN_TEXT,
        image=f"{IMAGE_RESOURCES_URL}/{pal_id}",
    )

    templates = wikicode.filter_templates()
    description_template = _find_template(templates, "Palpedia")
    if description_template is None:
        description_template = _find_template(templates, "Paldeck")
    drop_template = _find_template(
        templates,
        "Item Drop",
    )
    partner_skill_name = _optional_clean_parameter(
        pal_template,
        "partner_skill_name",
    )
    description = (
        _clean_wikitext(_parameter(description_template, "1"))
        if description_template
        else UNKNOWN_TEXT
    )
    if not description:
        description = UNKNOWN_TEXT

    record = {
        **pal.to_dict(),
        "description": description,
        "partnerSkill": _build_partner_skill(
            pal_template,
            partner_skill_name,
        ),
        "activeSkills": _parse_active_skills(
            _parameter(pal_template, "active_skills"),
            pal_name,
        )
        or [
            {
                "name": UNKNOWN_TEXT,
                "level": 0,
                "id": UNKNOWN_TEXT,
            }
        ],
        "possibleDrops": (
            _parse_drops(drop_template, pal_name)
            if drop_template
            else []
        )
        or [
            {
                "name": UNKNOWN_TEXT,
                "id": UNKNOWN_TEXT,
                "amount": "0",
                "dropRate": 0,
                "dropType": UNKNOWN_TEXT,
            }
        ],
        "food": _parse_integer_parameter(pal_template, "hunger", pal_name),
    }
    return record


def _build_partner_skill(
    pal_template: Template,
    partner_skill_name: Optional[str],
) -> dict:
    description = _optional_clean_parameter(
        pal_template,
        "partner_skill_desc",
    )
    if not partner_skill_name:
        partner_skill_name = UNKNOWN_TEXT
    if not description:
        description = UNKNOWN_TEXT
    return {
        "name": partner_skill_name,
        "description": description,
        "id": slugify(partner_skill_name),
    }


def _parse_work_suitability(
    raw_value: str,
    pal_name: str,
) -> List[Tuple[str, str, int]]:
    suitability = []
    for entry in _split_list(raw_value):
        name, level = _split_name_and_number(entry, "@", pal_name)
        normalized_name = re.sub(r"\s+", " ", name).strip().lower()
        try:
            suitability_id, display_name = WORK_SUITABILITY_NAMES[
                normalized_name
            ]
        except KeyError as error:
            raise ScraperError(
                f"{pal_name} has unknown work suitability {name!r}"
            ) from error
        suitability.append((suitability_id, display_name, level))
    return suitability


def _parse_active_skills(raw_value: str, pal_name: str) -> list:
    skills = []
    for entry in _split_list(raw_value):
        name, level = _split_name_and_number(entry, "@", pal_name)
        clean_name = _clean_wikitext(name)
        if clean_name and "???" not in clean_name:
            skills.append(
                {
                    "name": clean_name,
                    "level": level,
                    "id": slugify(clean_name),
                }
            )
    return skills


def _parse_drops(template: Template, pal_name: str) -> list:
    return [
        *_parse_drop_list(
            _parameter(template, "normal_drops"),
            "regular",
            pal_name,
        ),
        *_parse_drop_list(
            _parameter(template, "alpha_drops"),
            "alpha",
            pal_name,
        ),
    ]


def _parse_drop_list(
    raw_value: str,
    drop_type: str,
    pal_name: str,
) -> list:
    drops = []
    for entry in _split_list(raw_value):
        try:
            item_and_amount, rate_text = entry.rsplit("@", 1)
            item_name, amount = item_and_amount.rsplit("*", 1)
            drop_rate = _parse_number(rate_text)
        except (ValueError, TypeError) as error:
            raise ScraperError(
                f"{pal_name} has an invalid {drop_type} drop {entry!r}"
            ) from error

        clean_name = _clean_wikitext(item_name)
        if not clean_name:
            raise ScraperError(
                f"{pal_name} has a {drop_type} drop without a name"
            )
        drops.append(
            {
                "name": clean_name,
                "id": slugify(clean_name),
                "amount": amount.strip().replace("–", "-"),
                "dropRate": drop_rate,
                "dropType": drop_type,
            }
        )
    return drops


def download_pal_image(
    pal_name: str,
    pal_id: str,
    image_url: str,
    output_dir: Path = Path("output/images/pals"),
    session: Optional[requests.Session] = None,
) -> Path:
    """Download an API-resolved Pal icon atomically."""
    client = session or create_session()
    output_path = Path(output_dir) / f"{pal_id}.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    response = client.get(
        image_url,
        stream=True,
        timeout=REQUEST_TIMEOUT,
        headers={"Accept": "image/*"},
    )
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "")
    if "image/png" not in content_type.lower():
        raise ScraperError(
            f"Expected a PNG for {pal_name}, received {content_type!r}"
        )

    download_path = output_path.with_suffix(".png.download")
    normalized_path = output_path.with_suffix(".png.tmp")
    try:
        with download_path.open("wb") as output_file:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if chunk:
                    output_file.write(chunk)
        _normalize_png(download_path, normalized_path)
        normalized_path.replace(output_path)
    finally:
        download_path.unlink(missing_ok=True)
        normalized_path.unlink(missing_ok=True)
    return output_path


def _normalize_png(source_path: Path, output_path: Path) -> None:
    """Write a consistently sized PNG while preserving its aspect ratio."""
    try:
        with Image.open(source_path) as source_image:
            source_image.load()
            image = source_image.convert("RGBA")
    except (OSError, UnidentifiedImageError) as error:
        raise ScraperError(f"Downloaded file is not a valid image: {error}") from error

    normalized = ImageOps.pad(
        image,
        OUTPUT_IMAGE_SIZE,
        method=Image.Resampling.LANCZOS,
        color=(0, 0, 0, 0),
        centering=(0.5, 0.5),
    )
    optimized = normalized.quantize(
        colors=OUTPUT_IMAGE_COLORS,
        method=Image.Quantize.FASTOCTREE,
    )
    optimized.save(
        output_path,
        format="PNG",
        optimize=True,
        compress_level=9,
    )


def _api_get(
    session: requests.Session,
    parameters: dict,
) -> dict:
    params = {
        "format": "json",
        "formatversion": "2",
        "maxlag": "5",
        **parameters,
    }
    response = session.get(API_URL, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    try:
        payload = response.json()
    except requests.exceptions.JSONDecodeError as error:
        raise ScraperError("MediaWiki API returned invalid JSON") from error
    if "error" in payload:
        api_error = payload["error"]
        raise ScraperError(
            "MediaWiki API error "
            f"{api_error.get('code', 'unknown')}: "
            f"{api_error.get('info', 'no details')}"
        )
    return payload


def _find_template(
    templates: Iterable[Template],
    expected_name: str,
) -> Optional[Template]:
    normalized_expected = _normalize_template_name(expected_name)
    for template in templates:
        if _normalize_template_name(str(template.name)) == normalized_expected:
            return template
    return None


def _parameter(
    template: Optional[Template],
    name: str,
) -> str:
    if template is None or not template.has(name, ignore_empty=False):
        return ""
    value = str(template.get(name).value)
    return re.sub(r"<!--.*?-->", "", value, flags=re.DOTALL).strip()


def _optional_clean_parameter(template: Template, name: str) -> Optional[str]:
    value = _clean_wikitext(_parameter(template, name))
    return value or None


def _parse_integer_parameter(
    template: Template,
    name: str,
    pal_name: str,
) -> int:
    raw_value = _parameter(template, name)
    if not raw_value:
        return 0
    try:
        return int(raw_value)
    except ValueError as error:
        raise ScraperError(
            f"{pal_name} has a non-integer {name} value {raw_value!r}"
        ) from error


def _split_name_and_number(
    entry: str,
    separator: str,
    pal_name: str,
) -> Tuple[str, int]:
    try:
        name, raw_number = entry.rsplit(separator, 1)
        return name.strip(), int(raw_number.strip())
    except ValueError as error:
        raise ScraperError(
            f"{pal_name} has an invalid list entry {entry!r}"
        ) from error


def _split_list(raw_value: str) -> List[str]:
    return [entry.strip() for entry in raw_value.split(";") if entry.strip()]


def _parse_number(raw_value: str):
    value = float(raw_value.strip())
    return int(value) if value.is_integer() else value


def _clean_wikitext(value: str) -> str:
    if not value:
        return ""
    wikicode = mwparserfromhell.parse(value)
    for template in wikicode.filter_templates(recursive=True):
        template_name = _normalize_template_name(str(template.name))
        if template_name in {"i", "icon"} and template.has("1"):
            wikicode.replace(template, str(template.get("1").value))
    clean_value = wikicode.strip_code(
        normalize=True,
        collapse=True,
    )
    return re.sub(r"\s+", " ", clean_value).strip()


def _normalize_template_name(name: str) -> str:
    return re.sub(r"[_\s]+", " ", name.strip()).lower()


def _normalize_title(title: str) -> str:
    return re.sub(r"[_\s]+", " ", str(title).strip()).casefold()


def _pal_id_sort_key(pal_id: str) -> Tuple[int, str]:
    match = re.fullmatch(r"(\d+)([A-Z]?)", pal_id)
    if not match:
        return (999999, pal_id)
    return (int(match.group(1)), match.group(2))


def _has_released_pal_id(wikitext: str) -> bool:
    wikicode = mwparserfromhell.parse(wikitext)
    pal_template = _find_template(wikicode.filter_templates(), "Pal")
    raw_id = _parameter(pal_template, "no")
    normalized_id = normalize_pal_id(raw_id)
    match = re.fullmatch(r"(\d+)([A-Z]?)", normalized_id)
    return bool(match and int(match.group(1)) > 0)


def _validate_unique_records(records: Sequence[dict]) -> None:
    names = set()
    pal_ids = set()
    for record in records:
        name = record["name"]
        pal_id = record["id"]
        if name in names or pal_id in pal_ids:
            raise ScraperError(
                f"MediaWiki returned a duplicate Pal name or ID: "
                f"{name} ({pal_id})"
            )
        names.add(name)
        pal_ids.add(pal_id)


def _batched(
    values: Sequence[str],
    batch_size: int,
) -> Iterable[Sequence[str]]:
    for start in range(0, len(values), batch_size):
        yield values[start : start + batch_size]
