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
print(response.text[:12000])
