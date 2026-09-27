import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup


URL = "https://jeudepaume.org/agenda/"
VENUE = "Jeu de Paume"


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
        return None

    day1, month1, year1, day2, month2, year2 = match.groups()

    try:
        start = f"{year1}-{MONTHS[month1.lower()]:02d}-{int(day1):02d}"
        end = f"{year2}-{MONTHS[month2.lower()]:02d}-{int(day2):02d}"
    except KeyError:
        return None

    return start, end


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
    seen = set()

    for link in soup.find_all("a", href=True):

        href = link["href"]

        if "/agenda/" not in href:
            continue

        title = link.get_text(" ", strip=True)

        if not title:
            continue

        # On cherche le bloc contenant les informations
        # de l'exposition.
        container = link

        for _ in range(4):
            if container.parent is None:
                break

            container = container.parent

            text = container.get_text(
                " ",
                strip=True,
            )

            if "Paris" in text and re.search(r"\d{4}", text):
                break

        text = container.get_text(" ", strip=True)

        # Le Jeu de Paume indique le lieu dans le bloc.
        # On ne conserve que Paris.
        if "Paris" not in text:
            continue

        dates = parse_date_range(text)

        if not dates:
            continue

        start, end = dates

        if href.startswith("/"):
            full_url = "https://jeudepaume.org" + href
        else:
            full_url = href

        key = (title, start, end)

        if key in seen:
            continue

        seen.add(key)

        exhibitions.append({
            "title": title,
            "venue": VENUE,
            "start": start,
            "end": end,
            "url": full_url,
        })

    if not exhibitions:
        raise RuntimeError(
            "Aucune exposition du Jeu de Paume à Paris "
            "n'a été détectée."
        )

    return exhibitions


def main():
    exhibitions = scrape()

    output = Path("data/exhibitions.json")

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
        f"Jeu de Paume : {len(exhibitions)} expositions récupérées."
    )


if __name__ == "__main__":
    main()
