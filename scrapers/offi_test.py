import re
from datetime import datetime
from urllib.parse import quote

import requests


HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Imago/1.0)"
}


VENUE_PAGES = {
    "Louvre":
        "https://www.offi.fr/expositions-musees/musee-du-louvre-2615.html",

    "Jeu de Paume":
        "https://www.offi.fr/expositions-musees/jeu-de-paume-2387.html",

    "Musée de l'Orangerie":
        "https://www.offi.fr/expositions-musees/musee-de-lorangerie-2889.html",

    "Musée d'Orsay":
        "https://www.offi.fr/expositions-musees/musee-dorsay-2897.html",

    "Maison Européenne de la Photographie":
        "https://www.offi.fr/expositions-musees/maison-europeenne-de-la-photographie-2699.html",

    "Institut du Monde Arabe":
        "https://www.offi.fr/expositions-musees/institut-du-monde-arabe-2504.html",

    "Musée des Arts Décoratifs":
        "https://www.offi.fr/expositions-musees/les-arts-decoratifs-1462.html",

    "Fondation Louis Vuitton":
        "https://www.offi.fr/expositions-musees/fondation-louis-vuitton-6084.html",

    "Bourse de Commerce – Pinault Collection":
        "https://www.offi.fr/expositions-musees/bourse-de-commerce-pinault-collection-6929.html",

    "MAC VAL":
        "https://www.offi.fr/expositions-musees/mac-val-1444.html",

    "Fondation Cartier":
        "https://www.offi.fr/expositions-musees/fondation-cartier-pour-lart-contemporain-2334.html",

    "Grand Palais":
        "https://www.offi.fr/expositions-musees/grand-palais-5399.html",

    "Petit Palais":
        "https://www.offi.fr/expositions-musees/petit-palais-2991.html",

    "Musée Marmottan Monet":
        "https://www.offi.fr/expositions-musees/marmottan-monet-2747.html",

    "Musée du Luxembourg":
        "https://www.offi.fr/expositions-musees/musee-du-luxembourg-2626.html",
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


DATE_PATTERN = re.compile(
    r"Du\s+"
    r"(\d{1,2})\s+([a-zéûôîà]+)\s+(\d{4})"
    r"\s+au\s+"
    r"(\d{1,2})\s+([a-zéûôîà]+)\s+(\d{4})",
    re.IGNORECASE,
)


def get_page(url):
    """
    Fetch the page through Jina Reader.

    This avoids depending directly on the HTML structure of
    L'Officiel and gives us a readable Markdown representation.
    """
    jina_url = "https://r.jina.ai/" + url

    response = requests.get(
        jina_url,
        timeout=60,
        headers=HEADERS,
    )

    response.raise_for_status()

    text = response.text.strip()

    if not text:
        raise RuntimeError("Réponse vide de Jina Reader.")

    return text


def parse_date(value):
    """
    Convert a French date such as:
    26 septembre 2026

    into:
    2026-09-26
    """
    parts = value.strip().lower().split()

    if len(parts) != 3:
        return None

    day = int(parts[0])
    month_name = parts[1]
    year = int(parts[2])

    month = MONTHS.get(month_name)

    if month is None:
        return None

    date = datetime(year, month, day)

    return date.strftime("%Y-%m-%d")


def extract_dates(text):
    """
    Extract a date range such as:

    Du 26 septembre 2026 au 14 février 2027
    """
    match = DATE_PATTERN.search(text)

    if not match:
        return None

    start = parse_date(
        f"{match.group(1)} {match.group(2)} {match.group(3)}"
    )

    end = parse_date(
        f"{match.group(4)} {match.group(5)} {match.group(6)}"
    )

    if start is None or end is None:
        return None

    return start, end


def clean_title(line):
    """
    Convert Markdown headings/links into a plain title.
    """

    title = line.strip()

    if title.startswith("#####"):
        title = title[5:].strip()

    # Markdown link:
    # [Titre](https://...)
    match = re.match(r"\[([^\]]+)\]\([^)]+\)", title)

    if match:
        title = match.group(1)

    # Remove remaining Markdown emphasis.
    title = title.replace("**", "")
    title = title.replace("__", "")

    return title.strip()


def extract_exhibitions(markdown, venue):
    """
    Extract only the exhibitions contained in the section
    "X événements programmés en Expositions".

    Previous exhibitions and permanent collections are therefore
    ignored.
    """

    lines = markdown.splitlines()

    section_start = None

    for index, line in enumerate(lines):
        if (
            "Événements programmés en Expositions" in line
            or "événements programmés en Expositions" in line
        ):
            section_start = index + 1
            break

    if section_start is None:
        raise RuntimeError(
            "Section 'Événements programmés en Expositions' introuvable."
        )

    section_end = len(lines)

    for index in range(section_start, len(lines)):
        line = lines[index].strip()

        if (
            line.startswith("## ")
            and "Événements programmés en Expositions" not in line
        ):
            section_end = index
            break

    section = lines[section_start:section_end]

    exhibitions = []

    for index, line in enumerate(section):

        stripped = line.strip()

        if not stripped.startswith("#####"):
            continue

        title = clean_title(stripped)

        if not title:
            continue

        # Ignore permanent collections explicitly.
        if "collections permanentes" in title.lower():
            continue

        # Search the lines immediately following the title
        # for the exhibition's date range.
        context = "\n".join(section[index:index + 15])

        dates = extract_dates(context)

        if dates is None:
            continue

        start, end = dates

        exhibitions.append({
            "title": title,
            "venue": venue,
            "start": start,
            "end": end,
        })

    return exhibitions


def scrape_venue(venue, url):
    print()
    print("=" * 80)
    print(f"{venue}")
    print(url)
    print("=" * 80)

    markdown = get_page(url)

    exhibitions = extract_exhibitions(
        markdown,
        venue,
    )

    print(
        f"{len(exhibitions)} exposition(s) détectée(s)."
    )

    for exhibition in exhibitions:
        print(
            f"- {exhibition['title']} | "
            f"{exhibition['venue']} | "
            f"{exhibition['start']} → "
            f"{exhibition['end']}"
        )

    return exhibitions


def main():
    all_exhibitions = []

    errors = []

    for venue, url in VENUE_PAGES.items():

        try:
            exhibitions = scrape_venue(
                venue,
                url,
            )

            all_exhibitions.extend(exhibitions)

        except Exception as error:
            print()
            print(
                f"ERREUR pour {venue}: {error}"
            )

            errors.append({
                "venue": venue,
                "error": str(error),
            })

    print()
    print()
    print("=" * 80)
    print("RÉSUMÉ DU TEST L'OFFICIEL")
    print("=" * 80)

    print(
        f"Pages testées : {len(VENUE_PAGES)}"
    )

    print(
        f"Expositions détectées : {len(all_exhibitions)}"
    )

    print(
        f"Erreurs : {len(errors)}"
    )

    print()

    print("EXPOSITIONS DÉTECTÉES")
    print("-" * 80)

    all_exhibitions.sort(
        key=lambda exhibition: (
            exhibition["start"],
            exhibition["venue"],
            exhibition["title"],
        )
    )

    for exhibition in all_exhibitions:
        print(
            f"{exhibition['title']} | "
            f"{exhibition['venue']} | "
            f"{exhibition['start']} → "
            f"{exhibition['end']}"
        )

    if errors:
        print()
        print("ERREURS")
        print("-" * 80)

        for error in errors:
            print(
                f"- {error['venue']} : "
                f"{error['error']}"
            )

    print()
    print("=" * 80)
    print("FIN DU TEST")
    print("=" * 80)

    # Important:
    # This script intentionally does NOT write anything to
    # data/exhibitions.json.


if __name__ == "__main__":
    main()
