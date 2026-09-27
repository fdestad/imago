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
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()

    pattern = (
        r"(\d{1,2})\s+([a-zéû]+)\s+(\d{4})"
        r"\s*[–-]\s*"
        r"(\d{1,2})\s+([a-zéû]+)\s+(\d{4})"
    )

    match = re.search(pattern, text, re.IGNORECASE)

    if not match:
        # Cas où la première date ne comporte pas d'année
        pattern = (
            r"(\d{1,2})\s+([a-zéû]+)"
            r"\s*[–-]\s*"
            r"(\d{1,2})\s+([a-zéû]+)\s+(\d{4})"
        )

        match = re.search(pattern, text, re.IGNORECASE)

        if not match:
            return None

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

    else:
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
            "User-Agent": "Mozilla/5.0 (compatible; Imago/1.0)"
        },
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    exhibitions = []

    # On travaille à partir des titres de niveau 2 et 3.
    # La structure actuelle du Louvre utilise :
    #
    # h2 = expositions à venir / sections
    # h3 = expositions
    #
    # On arrête complètement la collecte à
    # "Le Louvre ailleurs".

    stop_collecting = False

    for heading in soup.find_all(["h2", "h3"]):

        title = heading.get_text(" ", strip=True)

        if title == "Le Louvre ailleurs":
            stop_collecting = True
            break

        if stop_collecting:
            break

        # Les titres de sections ne sont pas des expositions.
        if title in {
            "Exposition d'actualité",
            "Artistes invités",
        }:
            continue

        # On ne traite que les titres de niveau 2/3
        # qui sont réellement suivis d'une carte.
        if heading.name not in {"h2", "h3"}:
            continue

        link = heading.find("a", href=True)

        if link:
            exhibition_title = link.get_text(" ", strip=True)
            href = link["href"]
        else:
            exhibition_title = title
            href = None

        if not exhibition_title:
            continue

        # Cherche le bloc parent contenant les informations
        # de cette exposition.
        container = heading.parent

        if container is None:
            continue

        text = container.get_text(" ", strip=True)

        # Si le parent immédiat ne contient pas les dates,
        # on remonte d'un niveau.
        if not re.search(r"\d{4}", text):
            if container.parent is not None:
                container = container.parent
                text = container.get_text(" ", strip=True)

        dates = parse_date_range(text)

        if not dates:
            continue

        start, end = dates

        if href:
            if href.startswith("/"):
                href = "https://www.louvre.fr" + href
        else:
            continue

        exhibitions.append({
            "title": exhibition_title,
            "venue": VENUE,
            "start": start,
            "end": end,
            "url": href,
        })

    # Protection essentielle :
    # une récupération vide ou manifestement incomplète
    # ne doit jamais écraser les données existantes.

    if len(exhibitions) < 5:
        raise RuntimeError(
            f"Seulement {len(exhibitions)} expositions Louvre "
            "détectées. Les données existantes ne seront pas remplacées."
        )

    # Suppression des doublons
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

    # On ne remplace que les données du Louvre.
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
        f"Louvre : {len(exhibitions)} expositions récupérées."
    )


if __name__ == "__main__":
    main()
