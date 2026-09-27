import json
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup


AGENDA_URL = "https://jeudepaume.org/agenda/"
BASE_URL = "https://jeudepaume.org"
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


HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Imago/1.0)"
}


def parse_date_range(text):
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()

    # Exemple :
    # Du 20 octobre 2026 au 10 janvier 2027
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
    # Du 12 juin au 27 septembre 2026
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

    # On ne regarde que la section "Nos expositions du moment".
    section = None

    for heading in soup.find_all(["h2", "h3"]):
        if heading.get_text(" ", strip=True) == "Nos expositions du moment":
            section = heading
            break

    if section is None:
        raise RuntimeError(
            "Section 'Nos expositions du moment' introuvable."
        )

    links = []

    # On parcourt les liens situés après le titre de section,
    # mais uniquement jusqu'à la prochaine grande section.
    current = section

    for element in section.parent.find_all("a", href=True):
        href = element["href"]

        if "/evenement/" not in href:
            continue

        if href.startswith("/"):
            href = BASE_URL + href

        if href not in links:
            links.append(href)

    return links


def scrape_exhibition(url):
    response = requests.get(
        url,
        timeout=30,
        headers=HEADERS,
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    page_text = soup.get_text(" ", strip=True)

    # Une page individuelle doit explicitement être située
    # au Jeu de Paume - Paris.
    if "Jeu de Paume - Paris" not in page_text:
        return None

    # Le type doit être "Exposition".
    # On regarde les premiers éléments de la page pour éviter
    # de confondre avec les nombreuses occurrences du mot
    # "exposition" dans le programme.
    early_text = page_text[:3000]

    if not re.search(r"\bExposition\b", early_text):
        return None

    # Titre principal.
    h1 = soup.find("h1")

    if h1 is None:
        return None

    main_title = h1.get_text(" ", strip=True)

    if not main_title:
        return None

    # Sous-titre éventuel.
    # Pour Stan Douglas, par exemple :
    # h1 = Stan Douglas
    # h2 = Parallax
    subtitle = None

    for h2 in soup.find_all("h2"):
        candidate = h2.get_text(" ", strip=True)

        if candidate and candidate.lower() not in {
            "infos pratiques",
            "informations pratiques",
            "programme de la semaine",
            "expositions",
            "activités",
            "cinéma",
        }:
            subtitle = candidate
            break

    if subtitle:
        title = f"{main_title} — {subtitle}"
    else:
        title = main_title

    dates = parse_date_range(page_text)

    if not dates:
        return None

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
                f"Erreur lors de la récupération de {url}: {error}"
            )

    if len(exhibitions) == 0:
        raise RuntimeError(
            "Aucune exposition parisienne détectée au Jeu de Paume. "
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

    # On ne remplace que les données du Jeu de Paume.
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
