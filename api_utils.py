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


def build_heatmap(occurrences: list[dict], species_name: str):
    """
    Build a Folium map with a HeatMap density layer.
    Blue (sparse) → red (dense) gradient.
    Returns folium.Map.
    """
    import folium
    from folium.plugins import HeatMap

    m = folium.Map(location=[20.0, 0.0], zoom_start=2, tiles="CartoDB positron")

    heat_data = [[o["lat"], o["lon"]] for o in occurrences]
    if heat_data:
        HeatMap(
            heat_data,
            name="Sighting Density",
            radius=13,
            blur=18,
            min_opacity=0.3,
            gradient={
                "0.2": "blue",
                "0.45": "cyan",
                "0.65": "lime",
                "0.85": "orange",
                "1.0": "red",
            },
        ).add_to(m)

    folium.LayerControl().add_to(m)
    return m


def build_animated_map(occurrences: list[dict], species_name: str):
    """
    Build a Folium map with TimestampedGeoJson animation.
    Points appear over time with a playback slider and auto-play.
    Returns folium.Map.
    """
    import json as _json
    import folium
    from folium.plugins import TimestampedGeoJson

    m = folium.Map(location=[20.0, 0.0], zoom_start=2, tiles="CartoDB positron")

    features = []
    for o in occurrences:
        year = o.get("year") or "2000"
        month = o.get("month") or 1
        try:
            timestamp = f"{int(year):04d}-{int(month):02d}-01"
        except (ValueError, TypeError):
            timestamp = "2000-01-01"

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [o["lon"], o["lat"]],
            },
            "properties": {
                "time": timestamp,
                "popup": (
                    f"<b>{species_name}</b><br>"
                    f"📍 {o.get('locality', 'Unknown')}<br>"
                    f"📅 {year}"
                ),
                "icon": "circle",
                "iconstyle": {
                    "fillColor": "#e25822",
                    "fillOpacity": 0.7,
                    "stroke": True,
                    "color": "#fff",
                    "weight": 1,
                    "radius": 5,
                },
            },
        })

    if features:
        TimestampedGeoJson(
            data={"type": "FeatureCollection", "features": features},
            period="P1M",           # step = 1 month
            duration="P1M",
            auto_play=False,
            loop=False,
            max_speed=5,
            loop_button=True,
            date_options="YYYY-MM",
            time_slider_drag_update=True,
        ).add_to(m)

    return m


def build_marker_map(occurrences: list[dict], species_name: str):
    """Build a Folium map with clustered circle markers (original view)."""
    import folium
    from folium.plugins import MarkerCluster

    m = folium.Map(location=[20.0, 0.0], zoom_start=2, tiles="CartoDB positron")
    cluster = MarkerCluster(name="Sightings").add_to(m)

    for occ in occurrences:
        popup_text = (
            f"<b>{species_name}</b><br>"
            f"📍 {occ['locality']}<br>"
            f"📅 {occ['year']}"
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


def geocode_location(query: str) -> tuple[float, float] | None:
    """
    Convert a city/place name to (lat, lon) using Nominatim (OpenStreetMap).
    Returns None if the location cannot be resolved.
    """
    try:
        from geopy.geocoders import Nominatim
        geolocator = Nominatim(user_agent="BirdIDApp/1.0")
        location = geolocator.geocode(query, timeout=8)
        if location:
            return (location.latitude, location.longitude)
    except Exception:
        pass
    return None


def get_nearby_sightings(
    occurrences: list[dict],
    user_lat: float,
    user_lon: float,
    radius_km: float = 50.0,
) -> list[dict]:
    """
    Filter occurrences within radius_km of (user_lat, user_lon).
    Returns observations sorted by distance (nearest first),
    with a 'distance_km' key added to each dict.
    """
    try:
        from geopy.distance import geodesic
    except ImportError:
        return []

    nearby = []
    user_point = (user_lat, user_lon)
    for o in occurrences:
        obs_point = (o["lat"], o["lon"])
        try:
            dist = geodesic(user_point, obs_point).km
        except Exception:
            continue
        if dist <= radius_km:
            nearby.append({**o, "distance_km": round(dist, 1)})

    nearby.sort(key=lambda x: x["distance_km"])
    return nearby


def build_nearby_map(
    nearby: list[dict],
    user_lat: float,
    user_lon: float,
    species_name: str,
) -> object:
    """
    Build a Folium map centred on user location with nearby sightings.
    User location shown as a blue marker; sightings as orange markers.
    """
    import folium

    m = folium.Map(location=[user_lat, user_lon], zoom_start=7, tiles="CartoDB positron")

    # User location marker
    folium.Marker(
        location=[user_lat, user_lon],
        popup="📍 Your location",
        icon=folium.Icon(color="blue", icon="home", prefix="fa"),
    ).add_to(m)

    for o in nearby:
        popup_text = (
            f"<b>{species_name}</b><br>"
            f"📍 {o.get('locality', 'Unknown')}<br>"
            f"📏 {o['distance_km']} km away<br>"
            f"📅 {o.get('year', '—')}"
        )
        folium.CircleMarker(
            location=[o["lat"], o["lon"]],
            radius=6,
            color="#e25822",
            fill=True,
            fill_color="#e25822",
            fill_opacity=0.75,
            popup=folium.Popup(popup_text, max_width=220),
        ).add_to(m)

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


# ── iNaturalist bird call audio ───────────────────────────────────────────────

def get_inaturalist_audio(scientific_name: str) -> dict | None:
    """
    Fetch a real bird call recording from iNaturalist observations.
    Returns a dict with: url, attribution, license, format.
    """
    try:
        r = requests.get(
            "https://api.inaturalist.org/v1/observations",
            params={
                "taxon_name": scientific_name,
                "per_page": 20,
                "sounds": "true",
                "quality_grade": "research",
            },
            timeout=10,
            headers={"User-Agent": "BirdIDApp/1.0"},
        )
        if r.status_code != 200:
            return None

        results = r.json().get("results", [])
        # Find the first observation that has a CC-licensed sound
        for obs in results:
            sounds = obs.get("sounds", [])
            for sound in sounds:
                url = sound.get("file_url", "")
                license_code = sound.get("license_code", "")
                attribution = sound.get("attribution", "iNaturalist contributor")
                place = obs.get("place_guess", "")
                date = obs.get("observed_on", "")
                if url and license_code:   # prefer CC-licensed
                    fmt = "audio/wav" if url.endswith(".wav") else "audio/mp4"
                    return {
                        "url": url,
                        "attribution": attribution,
                        "license": license_code.upper(),
                        "format": fmt,
                        "location": place,
                        "date": date,
                    }

        # Fallback: return first sound regardless of license
        for obs in results:
            sounds = obs.get("sounds", [])
            if sounds:
                sound = sounds[0]
                url = sound.get("file_url", "")
                if url:
                    fmt = "audio/wav" if url.endswith(".wav") else "audio/mp4"
                    return {
                        "url": url,
                        "attribution": sound.get("attribution", "iNaturalist contributor"),
                        "license": sound.get("license_code", "All rights reserved").upper(),
                        "format": fmt,
                        "location": obs.get("place_guess", ""),
                        "date": obs.get("observed_on", ""),
                    }
        return None
    except Exception:
        return None
