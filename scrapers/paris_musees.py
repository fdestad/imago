import json
import re
from datetime import datetime
from pathlib import Path

import requests


INDEX_URL = "https://parismusees.paris.fr/fr/expositions"
VENUE_SOURCE = "Paris Musées"

MONTHS = {
    1: 1,
    2: 2,
    3: 3,
    4: 4,
    5: 5,
    6: 6,
    7: 7,
    8: 8,
    9: 9,
    10: 10,
    11: 11,
    12: 12,
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Imago/1.0)"
}

VENUE_ALIASES = {
    "Maison de Balzac": "Maison de Balzac",
    "Maison de Victor Hugo - Hauteville House": "Maison de Victor Hugo",
    "Maison de Victor Hugo": "Maison de Victor Hugo",
    "Musée Bourdelle": "Musée Bourdelle",
    "Musée Carnavalet – Histoire de Paris": "Musée Carnavalet",
    "Musée Carnavalet": "Musée Carnavalet",
    "Musée Cernuschi, musée des Arts de l’Asie de la Ville de Paris": "Musée Cernuschi",
    "Musée Cernuschi": "Musée Cernuschi",
    "Musée Cognacq-Jay, le goût du XVIIIe": "Musée Cognacq-Jay",
    "Musée Cognacq-Jay": "Musée Cognacq-Jay",
    "Musée de la Libération de Paris - musée du Général Leclerc - musée Jean Moulin":
        "Musée de la Libération de Paris",
    "Musée de la Vie romantique": "Musée de la Vie romantique",
    "Musée d’Art Moderne de Paris": "Musée d’Art Moderne de Paris",
    "Musée d'Art Moderne de Paris": "Musée d’Art Moderne de Paris",
    "Musée d’Art moderne": "Musée d’Art Moderne de Paris",
    "Musée d'Art moderne": "Musée d’Art Moderne de Paris",
    "Musée Zadkine": "Musée Zadkine",
    "Palais Galliera, musée de la Mode de la Ville de Paris": "Palais Galliera",
    "Palais Galliera": "Palais Galliera",
    "Petit Palais, musée des Beaux-arts de la Ville de Paris": "Petit Palais",
    "Petit Palais": "Petit Palais",
    "Catacombes de Paris": "Catacombes de Paris",
    "Crypte archéologique de l'île de la Cité": "Crypte archéologique de l'île de la Cité",
}


def get_page(url):
    response = requests.get(
        "https://r.jina.ai/" + url,
        timeout=60,
        headers=HEADERS,
    )
    response.raise_for_status()

    if not response.text.strip():
        raise RuntimeError("Réponse vide de Jina Reader.")

    return response.text


def parse_dates(text):
    pattern = re.search(
        r"(?P<day1>\d{1,2})\s+"
        r"(?P<month1>\d{2})/(?P<year1>\d{2})\s*>\s*"
        r"(?P<day2>\d{1,2})\s+"
        r"(?P<month2>\d{2})/(?P<year2>\d{2})",
        text,
    )

    if not pattern:
        return None

    day1 = int(pattern.group("day1"))
    month1 = int(pattern.group("month1"))
    year1 = 2000 + int(pattern.group("year1"))

    day2 = int(pattern.group("day2"))
    month2 = int(pattern.group("month2"))
    year2 = 2000 + int(pattern.group("year2"))

    start = datetime(year1, month1, day1)
    end = datetime(year2, month2, day2)

    return (
        start.strftime("%Y-%m-%d"),
        end.strftime("%Y-%m-%d"),
    )


def find_venue(text):
    matches = []

    for alias, canonical in VENUE_ALIASES.items():
        position = text.find(alias)

        if position != -1:
            matches.append((position, alias, canonical))

    if not matches:
        return None

    matches.sort(key=lambda item: item[0])

    return matches[0][2]


def find_exhibition_cards(markdown):
    date_pattern = re.compile(
        r"\[\d{1,2}\s+\d{2}/\d{2}\s*>\s*"
        r"\d{1,2}\s+\d{2}/\d{2}\s+Exposition\s+"
    )

    starts = [match.start() for match in date_pattern.finditer(markdown)]

    cards = []

    for index, start in enumerate(starts):
        if index + 1 < len(starts):
            end = starts[index + 1]
        else:
            end = len(markdown)

        card = markdown[start:end]
        cards.append(card)

    return cards


def extract_exhibition(card):
    dates = parse_dates(card)

    if dates is None:
        return None

    start, end = dates

    venue = find_venue(card)

    if venue is None:
        print("Musée introuvable dans la carte :")
        print(card[:500])
        return None

    pattern = re.compile(
        r"https://parismusees\.paris\.fr"
        r"/fr/exposition/"
        r"[A-Za-z0-9À-ÿ._~:/?#\[\]@!$&'()*+,;=%-]+"
        r"\s+"
        r'"(?P<title>[^"]+)"'
    )

    matches = list(pattern.finditer(card))

    if not matches:
        print("Lien d'exposition introuvable dans la carte :")
        print(card[:500])
        return None

    match = matches[-1]

    url = match.group(0).split('"')[0]
    title = match.group("title").strip()

    return {
        "title": title,
        "venue": venue,
        "start": start,
        "end": end,
        "url": url,
    }


def scrape():
    markdown = get_page(INDEX_URL)

    cards = find_exhibition_cards(markdown)

    print(f"{len(cards)} carte(s) d'exposition trouvée(s).")

    exhibitions = []

    for card in cards:
        exhibition = extract_exhibition(card)

        if exhibition:
            exhibitions.append(exhibition)

    if not exhibitions:
        raise RuntimeError(
            "Aucune exposition Paris Musées détectée. "
            "Les données existantes ne seront pas remplacées."
        )

    unique = {}

    for exhibition in exhibitions:
        key = (
            exhibition["title"],
            exhibition["venue"],
            exhibition["start"],
            exhibition["end"],
        )
        unique[key] = exhibition

    exhibitions = list(unique.values())

    print("Expositions Paris Musées détectées :")

    for exhibition in exhibitions:
        print(
            f"- {exhibition['title']} | "
            f"{exhibition['venue']} | "
            f"{exhibition['start']} → "
            f"{exhibition['end']}"
        )

    return exhibitions


def main():
    exhibitions = scrape()

    output = Path("data/exhibitions.json")
    output.parent.mkdir(parents=True, exist_ok=True)

    existing = []

    if output.exists():
        with output.open("r", encoding="utf-8") as file:
            existing = json.load(file)

    paris_musees_venues = set(VENUE_ALIASES.values())

    other_venues = [
        exhibition
        for exhibition in existing
        if exhibition.get("venue") not in paris_musees_venues
    ]

    combined = other_venues + exhibitions

    with output.open("w", encoding="utf-8") as file:
        json.dump(
            combined,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print(
        f"Paris Musées : {len(exhibitions)} exposition(s) récupérée(s)."
    )


if __name__ == "__main__":
    main()
