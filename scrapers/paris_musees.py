import json
import re
from datetime import datetime
from pathlib import Path

import requests


INDEX_URL = "https://parismusees.paris.fr/fr/expositions"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Imago/1.0)"
}

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


PARIS_MUSEES = {
    "Maison de Balzac",
    "Maison de Victor Hugo - Hauteville House",
    "Maison de Victor Hugo",
    "Musée Bourdelle",
    "Musée Carnavalet – Histoire de Paris",
    "Musée Carnavalet",
    "Musée Cernuschi, musée des Arts de l’Asie de la Ville de Paris",
    "Musée Cernuschi",
    "Musée Cognacq-Jay, le goût du XVIIIe",
    "Musée Cognacq-Jay",
    "Musée de la Libération de Paris - musée du Général Leclerc - musée Jean Moulin",
    "Musée de la Vie romantique",
    "Musée d’Art Moderne de Paris",
    "Musée d'Art Moderne de Paris",
    "Musée Zadkine",
    "Palais Galliera, musée de la Mode de la Ville de Paris",
    "Palais Galliera",
    "Petit Palais, musée des Beaux-arts de la Ville de Paris",
    "Petit Palais",
    "Catacombes de Paris",
    "Crypte archéologique de l'île de la Cité",
}


def reader_url(url):
    return "https://r.jina.ai/" + url


def get_page(url):
    response = requests.get(
        reader_url(url),
        timeout=60,
        headers=HEADERS,
    )
    response.raise_for_status()

    if not response.text.strip():
        raise RuntimeError(f"Réponse vide pour {url}")

    return response.text


def parse_date_range(text):
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()

    # Du 15 septembre 2026 au 24 janvier 2027
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

    # Jusqu'au 24 janvier 2027
    pattern = (
        r"Jusqu['’]au\s+"
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


def get_exhibition_links():
    markdown = get_page(INDEX_URL)

    links = []

    # Jina échappe la syntaxe Markdown de la page.
    # On cherche donc directement les URL des fiches
    # individuelles d'exposition.
    pattern = (
        r"https://parismusees\.paris\.fr"
        r"/fr/exposition/"
        r"[A-Za-z0-9À-ÿ._~:/?#\[\]@!$&'()*+,;=%-]+"
    )

    for match in re.finditer(pattern, markdown):
        url = match.group(0)

        # Nettoyage éventuel des caractères ajoutés par Markdown
        url = url.rstrip("\\)\"'")

        if url not in links:
            links.append(url)

    print(f"{len(links)} lien(s) d'exposition détecté(s).")

    for url in links:
        print(f"  {url}")

    if not links:
        raise RuntimeError(
            "Aucune fiche d'exposition trouvée sur Paris Musées."
        )

    return links

def extract_title(markdown):
    for line in markdown.splitlines():
        line = line.strip()

        if line.startswith("# "):
            title = line[2:].strip()

            if title:
                return title

    return None


def extract_museum(markdown):
    for line in markdown.splitlines():
        clean = line.strip()

        for museum in PARIS_MUSEES:
            if museum in clean:
                return museum

    return None


def scrape_exhibition(url):
    markdown = get_page(url)

    # La fiche doit correspondre à une exposition.
    if not re.search(
        r"\bExposition\b",
        markdown,
        re.IGNORECASE,
    ):
        print(f"Pas une exposition : {url}")
        return None

    title = extract_title(markdown)

    if not title:
        print(f"Titre introuvable : {url}")
        return None

    museum = extract_museum(markdown)

    if not museum:
        print(f"Musée introuvable : {title}")
        return None

    dates = parse_date_range(markdown)

    if dates is None:
        raise RuntimeError(
            f"Dates introuvables pour : {title}"
        )

    start, end = dates

    return {
        "title": title,
        "venue": museum,
        "start": start,
        "end": end,
        "url": url,
    }


def scrape():
    links = get_exhibition_links()

    print(
        f"{len(links)} fiche(s) Paris Musées trouvée(s)."
    )

    exhibitions = []

    for url in links:
        try:
            exhibition = scrape_exhibition(url)

            if exhibition:
                exhibitions.append(exhibition)

        except requests.RequestException as error:
            raise RuntimeError(
                f"Erreur réseau pour {url}: {error}"
            ) from error

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

    print("Expositions Paris Musées détectées:")

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
        with output.open("r", encoding="utf-8") as f:
            existing = json.load(f)

    # On supprime uniquement les musées explicitement couverts
    # par Paris Musées, sans toucher aux autres sources.
    other_venues = [
        exhibition
        for exhibition in existing
        if exhibition.get("venue") not in PARIS_MUSEES
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
        f"Paris Musées : "
        f"{len(exhibitions)} exposition(s) récupérée(s)."
    )


if __name__ == "__main__":
    main()
