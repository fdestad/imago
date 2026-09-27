import json
import re
from datetime import datetime
from pathlib import Path

import requests


SOURCE_URL = (
    "https://www.musee-orsay.fr/"
    "fr/programme/agenda/expositions"
)

READER_URL = (
    "https://r.jina.ai/"
    + SOURCE_URL
)

VENUE = "Musée d'Orsay"

MONTHS = {
    "janvier": 1,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Imago/1.0)"
}

EXCLUDED_CATEGORIES = {
    "Expérience immersive",
    "Exposition hors les murs",
}

ALLOWED_CATEGORIES = {
    "Exposition au musée",
    "Exposition contemporaine",
    "Accrochage",
    "Parcours",
    "Présentation exceptionnelle",
}


def parse_dates(text):
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()

    # Du 29 septembre 2026 au 10 janvier 2027
    pattern = (
        r"Du\s+"
        r"(\d{1,2})\s+([a-zéû]+)\s+(\d{4})"
        r"\s+au\s+"
        r"(\d{1,2})\s+([a-zéû]+)\s+(\d{4})"
    )

    match = re.search(pattern, text, re.IGNORECASE)

    if match:
        day1, month1, year1, day2, month2, year2 = match.groups()

        start = datetime(
            int(year1),
            MONTHS[month1.lower()],
            int(day1),
        )

        end = datetime(
            int(year2),
            MONTHS[month2.lower()],
            int(day2),
        )

        return (
            start.strftime("%Y-%m-%d"),
            end.strftime("%Y-%m-%d"),
        )

    # Du 30 septembre au 24 janvier 2027
    pattern = (
        r"Du\s+"
        r"(\d{1,2})\s+([a-zéû]+)"
        r"\s+au\s+"
        r"(\d{1,2})\s+([a-zéû]+)\s+(\d{4})"
    )

    match = re.search(pattern, text, re.IGNORECASE)

    if match:
        day1, month1, day2, month2, year2 = match.groups()

        start = datetime(
            int(year2),
            MONTHS[month1.lower()],
            int(day1),
        )

        end = datetime(
            int(year2),
            MONTHS[month2.lower()],
            int(day2),
        )

        return (
            start.strftime("%Y-%m-%d"),
            end.strftime("%Y-%m-%d"),
        )

    # Jusqu'au 06 décembre 2026
    pattern = (
        r"Jusqu'au\s+"
        r"(\d{1,2})\s+([a-zéû]+)\s+(\d{4})"
    )

    match = re.search(pattern, text, re.IGNORECASE)

    if match:
        day, month, year = match.groups()

        end = datetime(
            int(year),
            MONTHS[month.lower()],
            int(day),
        )

        return (
            None,
            end.strftime("%Y-%m-%d"),
        )

    return None


def get_page():
    response = requests.get(
        READER_URL,
        timeout=60,
        headers=HEADERS,
    )

    response.raise_for_status()

    if not response.text.strip():
        raise RuntimeError(
            "La réponse de Jina Reader est vide."
        )

    return response.text


def extract_blocks(markdown):
    """
    Transforme le Markdown en blocs correspondant
    aux expositions d'Orsay.

    On travaille entre les sections :
      ## Expositions en cours
      ## Expositions à venir
    """

    lines = markdown.splitlines()

    blocks = []

    current = []

    inside_exhibitions = False

    for line in lines:
        stripped = line.strip()

        # Entrée dans une section d'expositions.
        if stripped.startswith("## Expositions"):
            inside_exhibitions = True

            if current:
                blocks.append(current)
                current = []

            continue

        # Sortie lorsque commence une autre section de niveau 2.
        if (
            inside_exhibitions
            and stripped.startswith("## ")
            and not stripped.startswith("## Expositions")
        ):
            if current:
                blocks.append(current)

            current = []
            inside_exhibitions = False
            continue

        if not inside_exhibitions:
            continue

        # Chaque titre ### démarre une nouvelle fiche.
        if stripped.startswith("### "):
            if current:
                blocks.append(current)

            current = [stripped]
        elif current:
            current.append(stripped)

    if current:
        blocks.append(current)

    return blocks


def clean_title(line):
    title = re.sub(r"^###\s*", "", line).strip()

    # Nettoyage de quelques artefacts Markdown.
    title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", title)

    return title.strip()


def parse_block(block):
    if not block:
        return None

    title_line = None

    for line in block:
        if line.startswith("### "):
            title_line = line
            break

    if title_line is None:
        return None

    title = clean_title(title_line)

    if not title:
        return None

    text = " ".join(block)

    category = None

    for candidate in ALLOWED_CATEGORIES | EXCLUDED_CATEGORIES:
        if candidate in text:
            category = candidate
            break

    if category is None:
        return None

    if category in EXCLUDED_CATEGORIES:
        return None

    dates = parse_dates(text)

    if dates is None:
        return None

    start, end = dates

    return {
        "title": title,
        "venue": VENUE,
        "start": start,
        "end": end,
        "url": SOURCE_URL,
    }


def scrape():
    markdown = get_page()

    blocks = extract_blocks(markdown)

    exhibitions = []

    for block in blocks:
        exhibition = parse_block(block)

        if exhibition:
            exhibitions.append(exhibition)

    if not exhibitions:
        raise RuntimeError(
            "Aucune exposition du Musée d'Orsay détectée. "
            "Les données existantes ne seront pas remplacées."
        )

    unique = {}

    for exhibition in exhibitions:
        key = (
            exhibition["title"],
            exhibition["start"],
            exhibition["end"],
        )

        unique[key] = exhibition

    exhibitions = list(unique.values())

    print(
        "Expositions Orsay détectées :"
    )

    for exhibition in exhibitions:
        print(
            f"- {exhibition['title']} | "
            f"{exhibition['start']} → "
            f"{exhibition['end']}"
        )

    return exhibitions


def main():
    exhibitions = scrape()

    output = Path("data/exhibitions.json")

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    existing = []

    if output.exists():
        with output.open("r", encoding="utf-8") as f:
            existing = json.load(f)

    other_venues = [
        exhibition
        for exhibition in existing
        if exhibition.get("venue") != VENUE
    ]

    combined = other_venues + exhibitions

    with output.open("w", encoding="utf-8") as f:
        json.dump(
            combined,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(
        f"Musée d'Orsay : "
        f"{len(exhibitions)} exposition(s) récupérée(s)."
    )


if __name__ == "__main__":
    main()
