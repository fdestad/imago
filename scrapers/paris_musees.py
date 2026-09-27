import json
import re
from datetime import datetime
from pathlib import Path

import requests


INDEX_URL = "https://parismusees.paris.fr/fr/expositions"

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
    "Crypte archéologique de l'île de la Cité":
        "Crypte archéologique de l'île de la Cité",
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


def find_date_markers(markdown):
    pattern = re.compile(
        r"\[\d{1,2}\s+\d{2}/\d{2}\s*>\s*"
        r"\d{1,2}\s+\d{2}/\d{2}\s+Exposition\s+"
    )

    return list(pattern.finditer(markdown))


def find_exhibition_links(markdown):
    pattern = re.compile(
        r"\(?(https://parismusees\.paris\.fr"
        r"/fr/exposition/"
        r"[A-Za-z0-9À-ÿ._~:/?#\[\]@!$&'()*+,;=%-]+)"
        r"\)?"
        r"\s+"
        r'"(?P<title>[^"]+)"'
    )

    return list(pattern.finditer(markdown))


def extract_exhibitions(markdown):
    date_markers = find_date_markers(markdown)
    links = find_exhibition_links(markdown)

    exhibitions = []

    for link in links:
        link_position = link.start()

        previous_markers = [
            marker for marker in date_markers
            if marker.start() <= link_position
        ]

        if not previous_markers:
            continue

        marker = previous_markers[-1]

        next_markers = [
            item for item in date_markers
            if item.start() > marker.start()
        ]

        if next_markers:
            card_end = next_markers[0].start()
        else:
            card_end = len(markdown)

        card = markdown[marker.start():card_end]

        dates = parse_dates(card)

        if dates is None:
            continue

        start, end = dates

        venue = find_venue(card)

        if venue is None:
            print("Musée introuvable pour :")
            print(card[:500])
            continue

        title = link.group("title").strip()
        url = link.group(1).strip()

        if not title:
            continue

        exhibitions.append({
            "title": title,
            "venue": venue,
            "start": start,
            "end": end,
            "url": url,
        })

    return exhibitions


def scrape():
    markdown = get_page(INDEX_URL)

    exhibitions = extract_exhibitions(markdown)

    print(
        f"{len(exhibitions)} exposition(s) Paris Musées détectée(s)."
    )

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

    exhibitions.sort(
        key=lambda exhibition: (
            exhibition["start"],
            exhibition["venue"],
            exhibition["title"],
        )
    )

    print("Expositions Paris Musées détectées :")

    for exhibition in exhibitions:
        print(
            f"- {exhibition['title']} | "
            f"{exhibition['venue']} | "
            f"{exhibition['start']} → "
            f"{exhibition['end']} | "
            f"{exhibition['url']}"
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
