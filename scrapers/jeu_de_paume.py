import json
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://jeudepaume.org"
URL = f"{BASE_URL}/agenda/"
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
        start = (
            f"{year1}-"
            f"{MONTHS[month1.lower()]:02d}-"
            f"{int(day1):02d}"
        )

        end = (
            f"{year2}-"
            f"{MONTHS[month2.lower()]:02d}-"
            f"{int(day2):02d}"
        )
    except KeyError:
        return None

    return start, end


def is_exhibition_page(soup):
    """
    Vérifie que la fiche correspond bien à une exposition
    et non à une visite, conférence, projection, atelier, etc.
    """

    text = soup.get_text(" ", strip=True)

    # Le Jeu de Paume utilise normalement cette terminologie
    # sur les fiches d'exposition.
    exhibition_markers = [
        "Exposition",
        "exposition",
    ]

    return any(marker in text for marker in exhibition_markers)


def extract_exhibition(url):
    response = requests.get(
        url,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; Imago/1.0)"
        },
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    if not is_exhibition_page(soup):
        return None

    text = soup.get_text(" ", strip=True)

    # On ne conserve que les expositions à Paris.
    # Les fiches de Tours / en ligne sont ainsi exclues.
    if not re.search(r"\bParis\b", text):
        return None

    dates = parse_date_range(text)

    if not dates:
        return None

    start, end = dates

    # Titre principal de la fiche.
    title = None

    for selector in ["h1", "h2"]:
        heading = soup.select_one(selector)

        if heading:
            candidate = heading.get_text(" ", strip=True)

            if candidate:
                title = candidate
                break

    if not title:
        return None

    return {
        "title": title,
        "venue": VENUE,
        "start": start,
        "end": end,
        "url": url,
    }


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

    candidate_urls = set()

    # On collecte les liens vers les fiches de l'agenda.
    for link in soup.find_all("a", href=True):

        href = link["href"]

        full_url = urljoin(BASE_URL, href)

        if not full_url.startswith(BASE_URL):
            continue

        # On ignore les liens génériques.
        if full_url.rstrip("/") == URL.rstrip("/"):
            continue

        candidate_urls.add(full_url)

    exhibitions = []

    for url in sorted(candidate_urls):

        try:
            exhibition = extract_exhibition(url)

        except requests.RequestException:
            continue

        if exhibition:
            exhibitions.append(exhibition)

    # Suppression des doublons.
    unique = {}

    for exhibition in exhibitions:
        key = (
            exhibition["title"],
            exhibition["start"],
            exhibition["end"],
        )

        unique[key] = exhibition

    exhibitions = list(unique.values())

    # Protection contre un scraping vide.
    if not exhibitions:
        raise RuntimeError(
            "Aucune exposition du Jeu de Paume à Paris "
            "n'a été détectée. Les données existantes "
            "ne seront pas remplacées."
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
        f"Jeu de Paume : "
        f"{len(exhibitions)} expositions récupérées."
    )


if __name__ == "__main__":
    main()
