import json
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup


ORSAY_URL = (
    "https://www.musee-orsay.fr/fr/programme/agenda"
    "?types%5Bexhibition_event%5D=exhibition_event"
)

PROXY_URL = "https://r.jina.ai/http://www.musee-orsay.fr/fr/programme/agenda?types%5Bexhibition_event%5D=exhibition_event"

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


def parse_dates(text):
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
        PROXY_URL,
        timeout=60,
        headers=HEADERS,
    )

    response.raise_for_status()

    return response.text


def scrape():
    html = get_page()

    soup = BeautifulSoup(html, "html.parser")

    # On cherche explicitement la section "Expositions".
    heading = None

    for element in soup.find_all(["h2", "h3"]):
        if element.get_text(" ", strip=True) == "Expositions":
            heading = element
            break

    if heading is None:
        raise RuntimeError(
            "Section 'Expositions' introuvable dans la page Orsay."
        )

    exhibitions = []

    # Parcours des éléments suivant le titre "Expositions".
    for element in heading.find_all_next():

        # Une nouvelle section principale signifie que
        # nous avons quitté la section Expositions.
        if (
            element.name == "h2"
            and element is not heading
        ):
            break

        if element.name != "article":
            continue

        text = element.get_text(" ", strip=True)

        if not text:
            continue

        # Catégorie Orsay.
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
            continue

        # Règles Imago.
        if category in EXCLUDED_CATEGORIES:
            continue

        # Titre.
        title_element = element.find("h3")

        if title_element is None:
            continue

        title = title_element.get_text(" ", strip=True)

        if not title:
            continue

        # Lien.
        link = title_element.find("a", href=True)

        if link is None:
            link = element.find("a", href=True)

        if link is None:
            continue

        url = link["href"]

        if url.startswith("/"):
            url = "https://www.musee-orsay.fr" + url

        # Dates.
        dates = parse_dates(text)

        if dates is None:
            continue

        start, end = dates

        exhibitions.append({
            "title": title,
            "venue": VENUE,
            "start": start,
            "end": end,
            "url": url,
        })

    if not exhibitions:
        raise RuntimeError(
            "Aucune exposition du Musée d'Orsay détectée. "
            "Les données existantes ne seront pas remplacées."
        )

    # Suppression des doublons.
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
