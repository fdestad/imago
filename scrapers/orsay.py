import json
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup


INDEX_URL = "https://www.musee-orsay.fr/fr/programme/agenda/expositions"
BASE_URL = "https://www.musee-orsay.fr"

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
    "Exposition hors les murs",
}


def reader_url(url):
    return "https://r.jina.ai/" + url


def get_page(url):
    response = requests.get(
        reader_url(url),
        timeout=60,
        headers=HEADERS,
    )

    response.raise_for_status()

    if not response.text.strip():
        raise RuntimeError(
            f"Réponse vide pour {url}"
        )

    return response.text


def parse_date_range(text):
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()

    # Du 30 septembre 2026 au 24 janvier 2027
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

    # Jusqu'au 6 décembre 2026
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


def get_exhibition_links():
    markdown = get_page(INDEX_URL)

    links = []

    # Jina conserve les liens Markdown :
    # [Titre](https://www.musee-orsay.fr/...)
    pattern = (
        r"\]\((https://www\.musee-orsay\.fr"
        r"/fr/programme/agenda/expositions/"
        r"[^)\s]+)\)"
    )

    for match in re.finditer(pattern, markdown):
        url = match.group(1)

        if url not in links:
            links.append(url)

    if not links:
        raise RuntimeError(
            "Aucune fiche d'exposition trouvée "
            "sur la page Orsay."
        )

    return links


def find_category(text):
    categories = [
        "Exposition au musée",
        "Exposition contemporaine",
        "Accrochage",
        "Parcours",
        "Présentation exceptionnelle",
        "Expérience immersive",
        "Exposition hors les murs",
    ]

    positions = []

    for category in categories:
        position = text.find(category)

        if position != -1:
            positions.append((position, category))

    if not positions:
        return None

    positions.sort(key=lambda item: item[0])

    return positions[0][1]


def extract_title(markdown):
    for line in markdown.splitlines():
        line = line.strip()

        if line.startswith("# "):
            title = line[2:].strip()

            if title:
                return title

    return None


def scrape_exhibition(url):
    markdown = get_page(url)

    category = find_category(markdown)

    if category is None:
        print(
            f"Catégorie introuvable : {url}"
        )
        return None

    if category in EXCLUDED_CATEGORIES:
        print(
            f"Exposition hors les murs ignorée : {url}"
        )
        return None

    title = extract_title(markdown)

    if not title:
        print(
            f"Titre introuvable : {url}"
        )
        return None

    dates = parse_date_range(markdown)

    if dates is None:
        raise RuntimeError(
            f"Dates introuvables pour : {title}"
        )

    start, end = dates

    return {
        "title": title,
        "venue": VENUE,
        "start": start,
        "end": end,
        "url": url,
    }


def scrape():
    links = get_exhibition_links()

    print(
        f"{len(links)} fiche(s) Orsay trouvée(s)."
    )

    exhibitions = []

    for url in links:
        try:
            exhibition = scrape_exhibition(url)

            if exhibition:
                exhibitions.append(exhibition)

        except requests.RequestException as error:
            raise RuntimeError(
                f"Erreur réseau pour {url}: {error}"
            ) from error

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

    print("Expositions Orsay détectées :")

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
