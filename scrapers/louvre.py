import json
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup


URL = "https://www.louvre.fr/expositions-et-evenements/expositions"
VENUE = "Musée du Louvre"


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


def parse_date_range(text):
    """
    Convertit par exemple :
    '7 octobre 2026 – 25 janvier 2027'
    en deux dates ISO.
    """

    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()

    pattern = (
        r"(\d{1,2})\s+([a-zéû]+)\s+(\d{4})"
        r"\s*[–-]\s*"
        r"(\d{1,2})\s+([a-zéû]+)\s+(\d{4})"
    )

    match = re.search(pattern, text, re.IGNORECASE)

    if not match:
        return None

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


def scrape():
    response = requests.get(
        URL,
        timeout=30,
        headers={
            "User-Agent": "Imago exhibition collector"
        },
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    exhibitions = []

    # On récupère les liens vers les pages d'expositions.
    links = soup.find_all("a", href=True)

    seen = set()

    for link in links:
        href = link["href"]

        if "/expositions-et-evenements/expositions/" not in href:
            continue

        title = link.get_text(" ", strip=True)

        if not title:
            continue

        if href.startswith("/"):
            full_url = "https://www.louvre.fr" + href
        else:
            full_url = href

        if full_url in seen:
            continue

        seen.add(full_url)

        # Le bloc contenant le lien contient normalement
        # également les dates de l'exposition.
        container = link.parent

        if container is None:
            continue

        text = container.parent.get_text(
            " ",
            strip=True
        )

        dates = parse_date_range(text)

        if not dates:
            continue

        start, end = dates

        exhibitions.append({
            "title": title,
            "venue": VENUE,
            "start": start,
            "end": end,
            "url": full_url,
        })

    if not exhibitions:
        raise RuntimeError(
            "Le scraper Louvre n'a trouvé aucune exposition. "
            "Les données existantes ne doivent pas être remplacées."
        )

    return exhibitions


def main():
    exhibitions = scrape()

    output = Path("data/exhibitions.json")

    output.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # Pour cette première étape, on remplace uniquement
    # les données du Louvre.
    existing = []

    if output.exists():
        with output.open("r", encoding="utf-8") as f:
            existing = json.load(f)

    existing_without_louvre = [
        exhibition
        for exhibition in existing
        if exhibition.get("venue") != VENUE
    ]

    combined = existing_without_louvre + exhibitions

    with output.open("w", encoding="utf-8") as f:
        json.dump(
            combined,
            f,
            ensure_ascii=False,
            indent=2
        )

    print(
        f"Louvre : {len(exhibitions)} expositions récupérées."
    )


if __name__ == "__main__":
    main()
