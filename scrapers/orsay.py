import json
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup


URL = "https://www.musee-orsay.fr/fr/programme/agenda"
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


def parse_date_range(text):
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

        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    # Jusqu'au 31 janvier 2027
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

        # Pour une exposition déjà en cours, la date de début
        # doit être récupérée sur la fiche individuelle.
        return None, end.strftime("%Y-%m-%d")

    return None


def get_page():
    response = requests.get(
        URL,
        timeout=30,
        headers=HEADERS,
    )

    response.raise_for_status()

    return BeautifulSoup(response.text, "html.parser")


def get_exhibition_section(soup):
    for heading in soup.find_all(["h2", "h3"]):
        if heading.get_text(" ", strip=True) == "Expositions":
            return heading

    raise RuntimeError(
        "Section 'Expositions' introuvable sur l'agenda d'Orsay."
    )


def get_exhibition_cards(section):
    """
    Récupère les cartes situées dans la section Expositions.

    On s'arrête dès que l'on atteint la section suivante
    de l'agenda.
    """

    cards = []

    current = section

    while current is not None:
        current = current.find_next()

        if current is None:
            break

        # Une nouvelle section de niveau 2 marque la fin
        # de la section Expositions.
        if (
            current.name == "h2"
            and current.get_text(" ", strip=True) != "Expositions"
        ):
            break

        if current.name != "article":
            continue

        text = current.get_text(" ", strip=True)

        if not text:
            continue

        cards.append(current)

    return cards


def scrape_card(card):
    text = card.get_text(" ", strip=True)

    # Chercher la catégorie.
    category = None

    for candidate in [
        "Exposition au musée",
        "Exposition contemporaine",
        "Accrochage",
        "Parcours",
        "Présentation exceptionnelle",
        "Expérience immersive",
        "Exposition hors les murs",
    ]:
        if candidate in text:
            category = candidate
            break

    if category is None:
        return None

    # Exclusions décidées pour Imago.
    if category in EXCLUDED_CATEGORIES:
        return None

    # Le titre est généralement le H3 de la carte.
    heading = card.find("h3")

    if heading is None:
        return None

    title = heading.get_text(" ", strip=True)

    if not title:
        return None

    # URL de la fiche.
    link = heading.find("a", href=True)

    if link is None:
        link = card.find("a", href=True)

    if link is None:
        return None

    href = link["href"]

    if href.startswith("/"):
        href = "https://www.musee-orsay.fr" + href

    # Dates.
    dates = parse_date_range(text)

    if dates is None:
        return None

    start, end = dates

    # Certaines cartes n'affichent que "Jusqu'au..."
    # sur l'agenda. Dans ce cas, la fiche individuelle
    # est nécessaire pour récupérer la date de début.
    if start is None:
        return None

    return {
        "title": title,
        "venue": VENUE,
        "start": start,
        "end": end,
        "url": href,
    }


def scrape():
    soup = get_page()

    section = get_exhibition_section(soup)

    cards = get_exhibition_cards(section)

    exhibitions = []

    for card in cards:
        exhibition = scrape_card(card)

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

    return list(unique.values())


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
