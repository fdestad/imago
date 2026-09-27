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
    "01": 1,
    "02": 2,
    "03": 3,
    "04": 4,
    "05": 5,
    "06": 6,
    "07": 7,
    "08": 8,
    "09": 9,
    "10": 10,
    "11": 11,
    "12": 12,
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


def get_page():
    url = "https://r.jina.ai/" + INDEX_URL

    response = requests.get(
        url,
        timeout=60,
        headers=HEADERS,
    )

    response.raise_for_status()

    if not response.text.strip():
        raise RuntimeError(
            "Réponse vide de Paris Musées."
        )

    return response.text


def parse_date(day, month, year):
    return datetime(
        int(year),
        MONTHS[month],
        int(day),
    ).strftime("%Y-%m-%d")


def clean_text(text):
    text = text.replace("\\", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_exhibitions(markdown):
    """
    Extrait directement les cartes d'expositions de la page
    Paris Musées.

    Exemple de structure fournie par Jina :

    [15 09/26 > 24 01/27 Exposition Petit Palais ...
    Eva Gonzalès ...]
    (https://parismusees.paris.fr/fr/exposition/eva-gonzales-1847-1883)
    """

    exhibitions = []

    # Chaque fiche commence par un bloc de type :
    #
    # [15 09/26 > 24 01/27 Exposition Musée ...
    #
    # et contient ensuite l'URL /fr/exposition/...
    #
    pattern = re.compile(
        r"\["
        r"(?P<day1>\d{1,2})\s+"
        r"(?P<month1>\d{2})/"
        r"(?P<year1>\d{2})\s*>\s*"
        r"(?P<day2>\d{1,2})\s+"
        r"(?P<month2>\d{2})/"
        r"(?P<year2>\d{2})\s+"
        r"Exposition\s+"
        r"(?P<content>.*?)"
        r"\]\("
        r"\[?"
        r"(?P<url>https://parismusees\.paris\.fr"
        r"/fr/exposition/"
        r"[^)\s]+)"
        r"\)?",
        re.DOTALL,
    )

    for match in pattern.finditer(markdown):
        day1 = match.group("day1")
        month1 = match.group("month1")
        year1 = "20" + match.group("year1")

        day2 = match.group("day2")
        month2 = match.group("month2")
        year2 = "20" + match.group("year2")

        content = clean_text(match.group("content"))
        url = match.group("url")

        # Le contenu comprend :
        #
        # Musée
        # ![Image ...]
        # Titre
        #
        # On récupère le musée parmi notre liste connue.
        museum = None

        for candidate in sorted(
            PARIS_MUSEES,
            key=len,
            reverse=True,
        ):
            if candidate in content:
                museum = candidate
                break

        if museum is None:
            print(
                f"Musée introuvable pour : {url}"
            )
            continue

        # Le titre est généralement situé après le bloc image.
        # On supprime la partie image Markdown.
        title_content = re.sub(
            r"!\[[^\]]*\]\([^)]*\)",
            "",
            content,
        )

        title_content = clean_text(title_content)

        # Le nom du musée se trouve avant le titre.
        title_content = title_content.replace(
            museum,
            "",
            1,
        ).strip()

        if not title_content:
            print(
                f"Titre introuvable pour : {url}"
            )
            continue

        start = parse_date(
            day1,
            month1,
            year1,
        )

        end = parse_date(
            day2,
            month2,
            year2,
        )

        exhibitions.append({
            "title": title_content,
            "venue": museum,
            "start": start,
            "end": end,
            "url": url,
        })

    return exhibitions


def scrape():
    markdown = get_page()

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

    print("Expositions détectées :")

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

    # Ne supprimer que les données provenant des musées
    # explicitement couverts par Paris Musées.
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
