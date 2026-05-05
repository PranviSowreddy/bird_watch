"""
api_utils.py — Wikipedia summary + GBIF occurrence map helpers
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).parent
WIKI_CACHE = BASE_DIR / "cache" / "wiki_cache.json"

# ── Wikipedia ─────────────────────────────────────────────────────────────────

def _load_wiki_cache() -> dict:
    if WIKI_CACHE.exists():
        with open(WIKI_CACHE) as f:
            return json.load(f)
    return {}


def _save_wiki_cache(cache: dict) -> None:
    WIKI_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(WIKI_CACHE, "w") as f:
        json.dump(cache, f, indent=2)


def get_wikipedia_summary(species_name: str, scientific_name: str) -> str:
    """Fetch first paragraph from Wikipedia (cached)."""
    cache = _load_wiki_cache()
    key = species_name

    if key in cache:
        return cache[key]

    # Try common name first, then scientific name
    for query in [species_name, scientific_name]:
        try:
            url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + query.replace(" ", "_")
            r = requests.get(url, timeout=8, headers={"User-Agent": "BirdIDApp/1.0"})
            if r.status_code == 200:
                data = r.json()
                extract = data.get("extract", "")
                if extract and len(extract) > 50:
                    cache[key] = extract
                    _save_wiki_cache(cache)
                    return extract
        except Exception:
            pass
        time.sleep(0.3)

    fallback = f"No Wikipedia summary found for {species_name}."
    cache[key] = fallback
    _save_wiki_cache(cache)
    return fallback


# ── iNaturalist occurrence data ───────────────────────────────────────────────

def get_inaturalist_occurrences(
    scientific_name: str,
    limit: int = 200,
) -> list[dict]:
    """
    Fetch research-grade occurrence records from iNaturalist for a species globally.
    Returns list of dicts with keys: lat, lon, year, locality.
    """
    try:
        params: dict = {
            "taxon_name": scientific_name,
            "per_page": limit,
            "has": "geo",
            "quality_grade": "research"
        }

        r = requests.get(
            "https://api.inaturalist.org/v1/observations",
            params=params,
            timeout=10,
            headers={"User-Agent": "BirdIDApp/1.0"},
        )
        if r.status_code != 200:
            return []

        results = r.json().get("results", [])
        occurrences = []
        for rec in results:
            loc = rec.get("location")
            if loc:
                lat, lon = loc.split(",")
                date_str = rec.get("observed_on", "")
                year = ""
                month = 0
                if date_str:
                    parts = date_str.split("-")
                    year = parts[0]
                    if len(parts) > 1:
                        try:
                            month = int(parts[1])
                        except ValueError:
                            month = 0
                
                occurrences.append({
                    "lat": float(lat),
                    "lon": float(lon),
                    "year": year,
                    "month": month,
                    "locality": rec.get("place_guess") or "Unknown location",
                })
        return occurrences

    except Exception:
        return []


def build_folium_map(occurrences: list[dict], species_name: str):
    """Build a folium map with occurrence markers. Returns folium.Map."""
    import folium
    from folium.plugins import MarkerCluster

    # Centre on a global view for migrant bird visualization
    m = folium.Map(location=[20.0, 0.0], zoom_start=2, tiles="CartoDB positron")

    cluster = MarkerCluster(name="Sightings").add_to(m)
    for occ in occurrences:
        popup_text = (
            f"<b>{species_name}</b><br>"
            f"Locality: {occ['locality']}<br>"
            f"Year: {occ['year']}"
        )
        folium.CircleMarker(
            location=[occ["lat"], occ["lon"]],
            radius=5,
            color="#e25822",
            fill=True,
            fill_color="#e25822",
            fill_opacity=0.6,
            popup=folium.Popup(popup_text, max_width=200),
        ).add_to(cluster)

    folium.LayerControl().add_to(m)
    return m


# ── Kid's Corner (Gemini funny story) ────────────────────────────────────────

def get_kids_funny_story(
    species_name: str,
    metadata: dict,
    wiki_summary: str,
) -> str:
    """
    Use Gemini to generate a funny, kid-friendly story about the bird.
    Uses species metadata + Wikipedia as context (simple RAG).
    """
    import os
    import google.generativeai as genai

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return "⚠️ Set GOOGLE_API_KEY to enable the funny story!"

    try:
        genai.configure(api_key=api_key)

        model_to_use = "gemini-1.5-flash"
        try:
            available_models = [
                m.name for m in genai.list_models()
                if "generateContent" in m.supported_generation_methods
            ]
            if available_models:
                if "models/gemini-1.5-flash" in available_models:
                    model_to_use = "gemini-1.5-flash"
                elif "models/gemini-pro" in available_models:
                    model_to_use = "gemini-pro"
                else:
                    model_to_use = available_models[0].replace("models/", "")
        except Exception:
            pass

        model = genai.GenerativeModel(model_to_use)

        context = f"""
        SPECIES: {species_name}
        SCIENTIFIC NAME: {metadata.get('scientific_name')}
        DIET: {metadata.get('diet')}
        HABITAT: {metadata.get('habitat')}
        FUN FACT: {metadata.get('fun_fact')}
        WIKIPEDIA SUMMARY: {wiki_summary}
        """

        prompt = f"""You are a funny, energetic, and slightly silly bird expert talking to kids.
        Based on this bird's info:
        {context}

        Write a super funny and engaging introduction of this bird for a 7-year-old.
        Use emojis 🐦, funny comparisons (e.g. compare wingspan to pizza sizes or school buses),
        sound effects (WHOOSH! SQUAWK!), and a very friendly enthusiastic tone.
        Keep it under 180 words. Make it feel like a fun children's book page!
        """

        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Oops! The birds are hiding! 🙈 (Error: {str(e)})"


# ── Xeno-Canto bird call audio ────────────────────────────────────────────────

def get_xenocanto_audio(scientific_name: str) -> dict | None:
    """
    Fetch the best-quality bird call recording from Xeno-Canto API.
    Returns a dict with: url, recordist, location, type, quality.
    """
    try:
        r = requests.get(
            "https://xeno-canto.org/api/2/recordings",
            params={"query": f"{scientific_name} q:A"},
            timeout=8,
            headers={"User-Agent": "BirdIDApp/1.0"},
        )
        if r.status_code != 200:
            return None
        data = r.json()
        recordings = data.get("recordings", [])
        if not recordings:
            # Retry without quality filter
            r2 = requests.get(
                "https://xeno-canto.org/api/2/recordings",
                params={"query": scientific_name},
                timeout=8,
                headers={"User-Agent": "BirdIDApp/1.0"},
            )
            if r2.status_code == 200:
                recordings = r2.json().get("recordings", [])

        if recordings:
            rec = recordings[0]
            file_url = rec.get("file", "")
            # Xeno-Canto URLs need https
            if file_url.startswith("//"):
                file_url = "https:" + file_url
            return {
                "url": file_url,
                "recordist": rec.get("rec", "Unknown"),
                "location": f"{rec.get('loc', '')}, {rec.get('cnt', '')}".strip(", "),
                "type": rec.get("type", "call"),
                "quality": rec.get("q", "?"),
                "xc_id": rec.get("id", ""),
            }
        return None
    except Exception:
        return None
