import requests

URL = "https://r.jina.ai/https://parismusees.paris.fr/fr/expositions"

response = requests.get(
    URL,
    timeout=60,
    headers={
        "User-Agent": "Mozilla/5.0 (compatible; Imago/1.0)"
    },
)

response.raise_for_status()

print("STATUS:", response.status_code)
print("LENGTH:", len(response.text))
print()
text = response.text

for term in [
    "Tisser, broder, sublimer",
    "Hugo et l’architecture",
    "L’étoffe de l’artiste",
]:
    position = text.find(term)

    print("\n" + "=" * 80)
    print(term)
    print("=" * 80)

    if position == -1:
        print("INTROUVABLE")
    else:
        print(text[max(0, position - 1000):position + 1000])
