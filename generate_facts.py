"""
generate_facts.py — (Optional) Enrich species_data.json using Google Gemini

Run once if you want AI-generated fun facts & verify IUCN status:
  export GOOGLE_API_KEY="your-key"
  python generate_facts.py

The script reads cache/species_data.json, calls Gemini for any species
missing a fun_fact, and writes the enriched JSON back.
"""

import json
import os
import time
from pathlib import Path

SPECIES_DATA_PATH = Path("cache/species_data.json")


def generate_with_gemini(species_name: str, scientific_name: str) -> dict:
    """Ask Gemini for a fun fact + IUCN status."""
    try:
        import google.generativeai as genai

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set")

        genai.configure(api_key=api_key)
        
        # Try to find an available model dynamically
        model_to_use = "gemini-1.5-flash" 
        try:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            if available_models:
                if "models/gemini-1.5-flash" in available_models:
                    model_to_use = "gemini-1.5-flash"
                elif "models/gemini-pro" in available_models:
                    model_to_use = "gemini-pro"
                else:
                    model_to_use = available_models[0].replace("models/", "")
        except Exception:
            model_to_use = "gemini-1.5-flash"

        model = genai.GenerativeModel(model_to_use)

        prompt = f"""You are an ornithology expert. For the bird species "{species_name}" 
(scientific name: {scientific_name}), provide:
1. A single, surprising and engaging fun fact (2-3 sentences, no bullet points)
2. Its current IUCN Red List status code (one of: EX, EW, CR, EN, VU, NT, LC, DD, NE)

Respond ONLY in this exact JSON format, no other text:
{{
  "fun_fact": "...",
  "iucn_status": "LC"
}}"""

        response = model.generate_content(prompt)
        text = response.text.strip()

        # Strip markdown fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])

        return json.loads(text)

    except Exception as e:
        print(f"  Gemini error for {species_name}: {e}")
        return {}


def main():
    with open(SPECIES_DATA_PATH) as f:
        data = json.load(f)

    enriched = 0
    for species, info in data.items():
        has_fact = bool(info.get("fun_fact", "").strip())
        if has_fact:
            print(f"  ✓ {species} — already has fun fact")
            continue

        print(f"  ⏳ {species} — generating with Gemini…")
        result = generate_with_gemini(species, info.get("scientific_name", species))

        if result.get("fun_fact"):
            info["fun_fact"] = result["fun_fact"]
            enriched += 1
        if result.get("iucn_status"):
            info["iucn_status"] = result["iucn_status"]

        time.sleep(1.5)  # Avoid rate limiting

    with open(SPECIES_DATA_PATH, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nDone. Enriched {enriched} species. Saved to {SPECIES_DATA_PATH}")


if __name__ == "__main__":
    main()
