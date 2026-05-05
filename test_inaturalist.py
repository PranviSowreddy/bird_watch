import requests

def test_inat():
    url = "https://api.inaturalist.org/v1/observations"
    params = {
        "taxon_name": "Merops orientalis",
        "per_page": 5,
        "has": "geo",
        "quality_grade": "research"
    }
    r = requests.get(url, params=params)
    data = r.json()
    for res in data.get("results", []):
        loc = res.get("location")
        date = res.get("observed_on")
        place = res.get("place_guess")
        print(f"Loc: {loc}, Date: {date}, Place: {place}")

if __name__ == "__main__":
    test_inat()
