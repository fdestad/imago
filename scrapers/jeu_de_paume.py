import json
import re
from datetime import datetime
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

    # Exemple :
    # "Du 20 octobre 2026 au 10 janvier 2027"
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
    # "Du 12 juin au 27 septembre 2026"
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

    # L'agenda contient plusieurs types de contenus :
    # expositions, conférences, performances, cinéma,
    # visites, cours, etc.
    #
    # On ne collecte donc que les éléments explicitement
    # présentés dans la section "Nos expositions du moment".

    section = None

    for heading in soup.find_all(["h2", "h3"]):
        title = heading.get_text(" ", strip=True)

        if title == "Nos expositions du moment":
            section = heading
            break

    if section is None:
        raise RuntimeError(
            "Section 'Nos expositions du moment' introuvable."
        )

    # On remonte au conteneur de la section.
    container = section.parent

    if container is None:
        raise RuntimeError(
            "Conteneur de la section des expositions introuvable."
        )

    # Les liens de la section permettent d'identifier les
    # pages individuelles des expositions.
    links = container.find_all("a", href=True)

    seen_urls = set()

    for link in links:
        href = link["href"]

        if href.startswith("/"):
            href = "https://jeudepaume.org" + href

        if not href.startswith("https://jeudepaume.org/"):
            continue

        if href in seen_urls:
            continue

        seen_urls.add(href)

        # On récupère le texte du bloc contenant le lien.
        parent = link

        for _ in range(4):
            if parent.parent is not None:
                parent = parent.parent

        text = parent.get_text(" ", strip=True)

        # On ne garde que les expositions explicitement
        # situées à Paris.
        if "Jeu de Paume - Paris" not in text:
            continue

        dates = parse_date_range(text)

        if not dates:
            continue

        start, end = dates

        # Le titre du lien peut contenir "Exposition".
        title = link.get_text(" ", strip=True)

        if not title:
            continue

        title = re.sub(
            r"^Exposition\s+",
            "",
            title,
            flags=re.IGNORECASE,
        ).strip()

        exhibitions.append({
            "title": title,
            "venue": VENUE,
            "start": start,
            "end": end,
            "url": href,
        })

    # Une absence totale est anormale :
    # on empêche donc le scraper d'écraser les données
    # existantes avec une liste vide.
    if len(exhibitions) == 0:
        raise RuntimeError(
            "Aucune exposition parisienne détectée au Jeu de Paume."
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
        f"Jeu de Paume : "
        f"{len(exhibitions)} exposition(s) récupérée(s)."
    )


if __name__ == "__main__":
    main()
