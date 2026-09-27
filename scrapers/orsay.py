import json
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup


AGENDA_URL = "https://www.musee-orsay.fr/fr/programme/agenda/expositions"
VENUE = "Musée d'Orsay"
BASE_URL = "https://www.musee-orsay.fr"

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

    # Exemple :
    # Du 20 octobre 2026 au 21 février 2027
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

    # Exemple :
    # Du 22 septembre au 06 décembre 2026
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

        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    return None


def get_exhibition_links():
    response = requests.get(
        AGENDA_URL,
        timeout=30,
        headers=HEADERS,
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    links = []

    for link in soup.find_all("a", href=True):
        href = link["href"]

        if not href.startswith("/fr/programme/agenda/expositions/"):
            continue

        if href == "/fr/programme/agenda/expositions/":
            continue

        full_url = BASE_URL + href

        if full_url not in links:
            links.append(full_url)

    if not links:
        raise RuntimeError(
            "Aucune fiche d'exposition trouvée sur la page d'Orsay."
        )

    return links


def find_category(page_text):
    categories = [
        "Exposition au musée",
        "Exposition contemporaine",
        "Accrochage",
        "Parcours",
        "Présentation exceptionnelle",
        "Expérience immersive",
        "Exposition hors les murs",
    ]

    # La catégorie se trouve au début de la fiche,
    # avant le titre principal.
    beginning = page_text[:2500]

    positions = []

    for category in categories:
        position = beginning.find(category)

        if position != -1:
            positions.append((position, category))

    if not positions:
        return None

    positions.sort(key=lambda item: item[0])

    return positions[0][1]


def scrape_exhibition(url):
    response = requests.get(
        url,
        timeout=30,
        headers=HEADERS,
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    page_text = soup.get_text(" ", strip=True)

    category = find_category(page_text)

    if category is None:
        return None

    if category in EXCLUDED_CATEGORIES:
        return None

    h1 = soup.find("h1")

    if h1 is None:
        return None

    title = h1.get_text(" ", strip=True)

    if not title:
        return None

    dates = parse_date_range(page_text)

    if not dates:
        raise RuntimeError(
            f"Dates introuvables pour l'exposition : {title}"
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

    exhibitions = []

    for url in links:
        try:
            exhibition = scrape_exhibition(url)

            if exhibition:
                exhibitions.append(exhibition)

        except requests.RequestException as error:
            print(
                f"Erreur réseau pour {url}: {error}"
            )

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

    # On ne remplace que les données du Musée d'Orsay.
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
