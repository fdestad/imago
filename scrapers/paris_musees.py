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


def get_page(url):
    response = requests.get(
        "https://r.jina.ai/" + url,
        timeout=60,
        headers=HEADERS,
    )

    response.raise_for_status()

    if not response.text.strip():
        raise RuntimeError(
            f"Réponse vide pour {url}"
        )

    return response.text


def parse_date_range(text):
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()

    # Format : 13 décembre 2025 > 18 octobre 2026
    pattern = (
        r"(\d{1,2})\s+"
        r"(janvier|février|mars|avril|mai|juin|juillet|août|"
        r"septembre|octobre|novembre|décembre)\s+"
        r"(\d{4})\s*>\s*"
        r"(\d{1,2})\s+"
        r"(janvier|février|mars|avril|mai|juin|juillet|août|"
        r"septembre|octobre|novembre|décembre)\s+"
        r"(\d{4})"
    )

    match = re.search(
        pattern,
        text,
        re.IGNORECASE,
    )

    if match:
        (
            day1,
            month1,
            year1,
            day2,
            month2,
            year2,
        ) = match.groups()

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

    # Format plus court éventuellement utilisé par le site :
    # 13 12/25 > 18 10/26
    pattern = (
        r"(\d{1,2})\s+"
        r"(\d{2})/(\d{2})\s*>\s*"
        r"(\d{1,2})\s+"
        r"(\d{2})/(\d{2})"
    )

    match = re.search(
        pattern,
        text,
    )

    if match:
        (
            day1,
            month1,
            year1,
            day2,
            month2,
            year2,
        ) = match.groups()

        start = datetime(
            2000 + int(year1),
            int(month1),
            int(day1),
        )

        end = datetime(
            2000 + int(year2),
            int(month2),
            int(day2),
        )

        return (
            start.strftime("%Y-%m-%d"),
            end.strftime("%Y-%m-%d"),
        )

    return None


def extract_exhibition_links(markdown):
    pattern = (
        r"https://parismusees\.paris\.fr"
        r"/fr/exposition/"
        r"[A-Za-z0-9À-ÿ._~:/?#\[\]@!$&'()*+,;=%-]+"
    )

    links = []

    for match in re.finditer(pattern, markdown):
        url = match.group(0)

        url = url.rstrip(
            "\\)\"'"
        )

        if url not in links:
            links.append(url)

    return links


def extract_title(markdown):
    """
    Le titre principal des fiches Paris Musées est le premier
    titre Markdown de niveau 1.
    Le sous-titre apparaît ensuite et n'est donc pas récupéré.
    """

    for line in markdown.splitlines():
        line = line.strip()

        if line.startswith("# "):
            title = line[2:].strip()

            if title:
                return title

    return None


def extract_venue(markdown):
    """
    Identifie le musée à partir de la liste des musées Paris Musées.
    """

    for museum in sorted(
        PARIS_MUSEES,
        key=len,
        reverse=True,
    ):
        if museum in markdown:
            return museum

    return None


def scrape_exhibition(url):
    markdown = get_page(url)

    title = extract_title(markdown)

    if not title:
        print(
            f"Titre introuvable : {url}"
        )
        return None

    venue = extract_venue(markdown)

    if not venue:
        print(
            f"Musée introuvable : {title}"
        )
        return None

    dates = parse_date_range(markdown)

    if not dates:
        print(
            f"Dates introuvables : {title}"
        )
        return None

    start, end = dates

    return {
        "title": title,
        "venue": venue,
        "start": start,
        "end": end,
        "url": url,
    }


def scrape():
    index = get_page(INDEX_URL)

    links = extract_exhibition_links(index)

    print(
        f"{len(links)} lien(s) d'exposition détecté(s)."
    )

    if not links:
        raise RuntimeError(
            "Aucune fiche d'exposition trouvée sur Paris Musées."
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

    print(
        f"{len(exhibitions)} fiche(s) Paris Musées trouvée(s)."
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

    exhibitions = list(
        unique.values()
    )

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

    output = Path(
        "data/exhibitions.json"
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    existing = []

    if output.exists():
        with output.open(
            "r",
            encoding="utf-8",
        ) as f:
            existing = json.load(f)

    other_venues = [
        exhibition
        for exhibition in existing
        if exhibition.get("venue")
        not in PARIS_MUSEES
    ]

    combined = other_venues + exhibitions

    with output.open(
        "w",
        encoding="utf-8",
    ) as f:
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
