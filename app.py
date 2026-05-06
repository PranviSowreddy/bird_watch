"""
app.py — Indian Bird Species Identifier
Streamlit app: upload → top-3 predictions → species details + IUCN badge + habitat map
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st
from PIL import Image

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="🦜 Bird Watch",
    page_icon="🦜",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Load species metadata ──────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
SPECIES_DATA_PATH = BASE_DIR / "cache" / "species_data.json"

@st.cache_data
def load_species_data() -> dict:
    with open(SPECIES_DATA_PATH) as f:
        return json.load(f)

SPECIES_DATA = load_species_data()

# ── IUCN badge config ─────────────────────────────────────────────────────────
IUCN_CONFIG = {
    "EX":  {"label": "Extinct",              "color": "#000000", "text": "white"},
    "EW":  {"label": "Extinct in Wild",      "color": "#542344", "text": "white"},
    "CR":  {"label": "Critically Endangered","color": "#D4251C", "text": "white"},
    "EN":  {"label": "Endangered",           "color": "#FC7F3F", "text": "white"},
    "VU":  {"label": "Vulnerable",           "color": "#F9E814", "text": "black"},
    "NT":  {"label": "Near Threatened",      "color": "#CCE226", "text": "black"},
    "LC":  {"label": "Least Concern",        "color": "#60C659", "text": "white"},
    "DD":  {"label": "Data Deficient",       "color": "#D1D1C6", "text": "black"},
    "NE":  {"label": "Not Evaluated",        "color": "#FFFFFF",  "text": "black"},
}

RARITY_CONFIG = {
    "Common":   {"color": "#2ecc71", "icon": "●●●"},
    "Uncommon": {"color": "#f39c12", "icon": "●●○"},
    "Rare":     {"color": "#e74c3c", "icon": "●○○"},
}

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Global ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── Hero banner ── */
.hero {
    background: linear-gradient(135deg, #1a472a 0%, #2d6a4f 50%, #40916c 100%);
    border-radius: 16px;
    padding: 2.5rem 3rem;
    margin-bottom: 2rem;
    color: white;
    text-align: center;
}
.hero h1 { font-size: 2.4rem; font-weight: 700; margin: 0; }
.hero p  { font-size: 1.05rem; opacity: 0.9; margin-top: 0.5rem; }

/* ── Upload zone ── */
.upload-area {
    border: 2px dashed #40916c;
    border-radius: 12px;
    padding: 2rem;
    text-align: center;
    background: #f0faf4;
    margin-bottom: 1rem;
}

/* ── Prediction card ── */
.pred-card {
    background: white;
    border-radius: 14px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 0.9rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.08);
    border-left: 6px solid #40916c;
    transition: transform 0.15s;
}
.pred-card:hover { transform: translateY(-2px); }
.pred-card.rank-1 { border-left-color: #1b4332; }
.pred-card.rank-2 { border-left-color: #40916c; }
.pred-card.rank-3 { border-left-color: #95d5b2; }

.pred-name { font-size: 1.15rem; font-weight: 600; color: #1b4332; }
.pred-sci  { font-size: 0.82rem; color: #6b7280; font-style: italic; }
.pred-pct  { font-size: 1.3rem; font-weight: 700; color: #40916c; }

/* ── IUCN badge ── */
.iucn-badge {
    display: inline-block;
    padding: 0.3rem 0.9rem;
    border-radius: 20px;
    font-weight: 700;
    font-size: 0.85rem;
    letter-spacing: 0.05em;
}

/* ── Fun fact box ── */
.fun-fact {
    background: linear-gradient(135deg, #e8f5e9, #f1f8e9);
    border-left: 4px solid #43a047;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    font-size: 0.95rem;
    color: #2e7d32;
    margin: 1rem 0;
}

/* ── Stat pills ── */
.stat-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: #f3f4f6;
    border-radius: 20px;
    padding: 0.3rem 0.8rem;
    font-size: 0.82rem;
    font-weight: 500;
    color: #374151;
    margin: 0.25rem;
}

/* ── Section header ── */
.section-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: #1b4332;
    border-bottom: 2px solid #d1fae5;
    padding-bottom: 0.4rem;
    margin: 1.2rem 0 0.8rem 0;
}

/* ── Confidence bar ── */
.conf-bar-outer {
    background: #e5e7eb;
    border-radius: 8px;
    height: 10px;
    margin-top: 6px;
}
.conf-bar-inner {
    background: linear-gradient(90deg, #40916c, #95d5b2);
    border-radius: 8px;
    height: 10px;
}

/* ── Backend chip ── */
.backend-chip {
    background: #dbeafe;
    color: #1d4ed8;
    border-radius: 20px;
    padding: 0.2rem 0.7rem;
    font-size: 0.75rem;
    font-weight: 600;
}

/* ── Wiki box ── */
.wiki-box {
    background: #fafafa;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    font-size: 0.9rem;
    color: #374151;
    line-height: 1.6;
    border: 1px solid #e5e7eb;
}
</style>
""", unsafe_allow_html=True)


# ── Helper functions ───────────────────────────────────────────────────────────
def iucn_badge_html(code: str) -> str:
    cfg = IUCN_CONFIG.get(code, IUCN_CONFIG["NE"])
    return (
        f'<span class="iucn-badge" '
        f'style="background:{cfg["color"]};color:{cfg["text"]};">'
        f'{code} — {cfg["label"]}</span>'
    )


def confidence_bar_html(pct: float) -> str:
    width = int(pct * 100)
    return (
        f'<div class="conf-bar-outer">'
        f'<div class="conf-bar-inner" style="width:{width}%;"></div>'
        f'</div>'
    )


def rarity_html(rarity: str) -> str:
    cfg = RARITY_CONFIG.get(rarity, {"color": "#6b7280", "icon": "○○○"})
    return (
        f'<span class="stat-pill">'
        f'<span style="color:{cfg["color"]};font-size:1rem;">{cfg["icon"]}</span>'
        f'Rarity: <b>{rarity}</b>'
        f'</span>'
    )


@st.cache_resource(show_spinner=False)
def load_model():
    """Lazy-load model (cached for session)."""
    from model_utils import predict as _predict
    return _predict


@st.cache_data(show_spinner=False)
def cached_wiki(species: str, sci: str) -> str:
    from api_utils import get_wikipedia_summary
    return get_wikipedia_summary(species, sci)


@st.cache_data(show_spinner=False)
def cached_inaturalist(sci: str) -> list:
    from api_utils import get_inaturalist_occurrences
    return get_inaturalist_occurrences(sci)


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🦜 About")
    st.markdown(
        "This app identifies **25 common Indian bird species** "
        "from photos using deep learning.\n\n"
        "**Model:** EfficientNet-B0 fine-tuned on 22.6k bird images  \n"
        "**Fallback:** CLIP zero-shot classification\n\n"
        "**Data:** iNaturalist global occurrence records  \n"
        "**Status:** IUCN Red List"
    )
    st.divider()
    st.markdown("### 📋 Know more about birds")
    for sp_name in sorted(SPECIES_DATA.keys()):
        sp_info = SPECIES_DATA[sp_name]
        cfg = IUCN_CONFIG.get(sp_info["iucn_status"], IUCN_CONFIG["NE"])
        dot = f'<span style="color:{cfg["color"]};">●</span>'
        wiki_url = f"https://en.wikipedia.org/wiki/{sp_info.get('scientific_name', '').replace(' ', '_')}"
        st.markdown(f"{dot} [{sp_name}]({wiki_url})", unsafe_allow_html=True)
    st.divider()
    st.markdown(
        "**IUCN Legend**\n"
        "🟢 LC — Least Concern  \n"
        "🟡 NT — Near Threatened  \n"
        "🟡 VU — Vulnerable  \n"
        "🟠 EN — Endangered  \n"
        "🔴 CR — Critically Endangered"
    )


# ── Hero ───────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <h1>🦜 Bird Watch</h1>
  <p>Upload a photo to identify the species, conservation status, habitat, and more</p>
</div>
""", unsafe_allow_html=True)


# ── Upload ─────────────────────────────────────────────────────────────────────
col_up, col_hint = st.columns([2, 1])
with col_up:
    uploaded = st.file_uploader(
        "Upload a bird photo",
        type=["jpg", "jpeg", "png", "webp"],
        help="Best results with clear, unobstructed images of a single bird.",
    )
with col_hint:
    st.info(
        "📸 **Tips for best results**\n"
        "- Clear, well-lit photos\n"
        "- Single bird in frame\n"
        "- Avoid heavy blur\n"
        "- JPG / PNG / WebP"
    )


# ── Main analysis ──────────────────────────────────────────────────────────────
if uploaded is not None:
    image = Image.open(uploaded).convert("RGB")

    with st.spinner("Identifying species…"):
        predict_fn = load_model()
        predictions, backend = predict_fn(image, top_k=3)

    top_name, top_prob = predictions[0]
    sp = SPECIES_DATA.get(top_name, {})

    # ── Layout: image | predictions ─────────────────────────────────────────
    col_img, col_preds = st.columns([1, 1], gap="large")

    with col_img:
        st.markdown('<div class="section-title">📷 Uploaded Image</div>', unsafe_allow_html=True)
        st.image(image, use_container_width=True, caption=uploaded.name)

        # ── Bird Call Audio Player (Integrated from Kid's Corner) ───────────
        from api_utils import get_inaturalist_audio
        
        @st.cache_data(show_spinner=False)
        def cached_audio(sci: str):
            return get_inaturalist_audio(sci)

        audio_info = cached_audio(sp.get("scientific_name", top_name))

        if audio_info and audio_info.get("url"):
            st.markdown(
                f"""
                <div style="background:#f0fdf4;border-radius:12px;padding:0.8rem 1rem;
                            border:1px solid #bbf7d0;margin-top:1rem;font-size:0.85rem;">
                  🎵 <b>Bird Call:</b> {audio_info['attribution']}<br>
                  📍 {audio_info['location'] or 'Unknown'} &nbsp;|&nbsp; 📅 {audio_info['date'] or '—'}
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.audio(audio_info["url"], format=audio_info.get("format", "audio/mp4"))
        else:
            st.caption("No audio recording found for this species.")

    with col_preds:
        st.markdown('<div class="section-title">🔍 Top-3 Predictions</div>', unsafe_allow_html=True)

        st.markdown(
            f'<span class="backend-chip">Model: {backend}</span>',
            unsafe_allow_html=True,
        )
        st.write("")

        rank_classes = ["rank-1", "rank-2", "rank-3"]
        medals = ["🥇", "🥈", "🥉"]

        for i, (name, prob) in enumerate(predictions):
            sp = SPECIES_DATA.get(name, {})
            sci = sp.get("scientific_name", "")
            iucn_code = sp.get("iucn_status", "NE")

            card_html = f"""
            <div class="pred-card {rank_classes[i]}">
              <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                <div>
                  <span style="font-size:1.4rem;">{medals[i]}</span>
                  <span class="pred-name"> {name}</span><br>
                  <span class="pred-sci">{sci}</span>
                </div>
                <div style="text-align:right;">
                  <span class="pred-pct">{prob*100:.1f}%</span>
                </div>
              </div>
              {confidence_bar_html(prob)}
              <div style="margin-top:0.6rem;">
                {iucn_badge_html(iucn_code)}
                {rarity_html(sp.get("rarity",""))}
              </div>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)

    # ── Detailed info for top prediction ────────────────────────────────────
    st.divider()
    top_name, top_prob = predictions[0]
    sp = SPECIES_DATA.get(top_name, {})

    st.markdown(
        f"## 📖 Species Detail — **{top_name}**",
        help="Details are shown for the top-ranked prediction.",
    )

    # Fetch Wikipedia summary early
    with st.spinner("Fetching background info…"):
        wiki_text = cached_wiki(top_name, sp.get("scientific_name", ""))

    # Tab Order: Overview, Wikipedia, Habitat Map
    tab1, tab2, tab3 = st.tabs(["🌿 Overview", "📚 Wikipedia", "🗺️ Habitat Map"])

    # ── Tab 1: Overview ───────────────────────────────────────────────────────
    with tab1:
        c1, c2 = st.columns(2)

        with c1:
            st.markdown('<div class="section-title">Conservation & Identification</div>', unsafe_allow_html=True)

            iucn_code = sp.get("iucn_status", "NE")
            iucn_cfg = IUCN_CONFIG.get(iucn_code, IUCN_CONFIG["NE"])
            st.markdown(
                f"**IUCN Status:** {iucn_badge_html(iucn_code)}",
                unsafe_allow_html=True,
            )
            st.markdown(f"**Scientific Name:** *{sp.get('scientific_name','')}*")
            st.markdown(f"**Rarity in India:** {sp.get('rarity','')}")
            st.markdown(f"**Wingspan:** {sp.get('wingspan_cm','')} cm")
            st.markdown(f"**Diet:** {sp.get('diet','')}")
            st.markdown(f"**Habitat:** {sp.get('habitat','')}")

        with c2:
            st.markdown('<div class="section-title">🎉 Fun Fact</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="fun-fact">💡 {sp.get("fun_fact","")}</div>',
                unsafe_allow_html=True,
            )

            # Prediction confidence gauge
            st.markdown('<div class="section-title">Model Confidence</div>', unsafe_allow_html=True)
            for name, prob in predictions:
                st.markdown(
                    f"<small><b>{name}</b> — {prob*100:.1f}%</small>"
                    f"{confidence_bar_html(prob)}",
                    unsafe_allow_html=True,
                )
                st.write("")

    # ── Tab 2: Wikipedia ──────────────────────────────────────────────────────
    with tab2:
        st.markdown(f"### 📚 Wikipedia — {top_name}")
        st.markdown(
            f'<div class="wiki-box">{wiki_text}</div>',
            unsafe_allow_html=True,
        )
        sci_link = sp.get("scientific_name", top_name).replace(" ", "_")
        st.markdown(
            f"[→ Read full article on Wikipedia](https://en.wikipedia.org/wiki/{sci_link})",
            unsafe_allow_html=True,
        )

    # ── Tab 3: Global Migration & Habitat Map ─────────────────────────────────
    with tab3:
        st.markdown(
            f"### 🌍 Global Sightings & Migration Map — *{top_name}*  \n"
            "<small>Source: iNaturalist (Research-Grade Observations)</small>",
            unsafe_allow_html=True,
        )

        with st.spinner("Fetching global occurrence data from iNaturalist…"):
            occurrences = cached_inaturalist(
                sp.get("scientific_name", top_name)
            )

        if occurrences:
            # ── Month filter ────────────────────────────────────────────────
            months = ["All Year", "January", "February", "March", "April",
                      "May", "June", "July", "August", "September",
                      "October", "November", "December"]

            selected_month_name = st.select_slider(
                "📅 **Seasonal Migration Timeline**",
                options=months,
                value="All Year",
                help="Filter sightings by month across all map types.",
            )

            filtered_occurrences = occurrences
            if selected_month_name != "All Year":
                month_idx = months.index(selected_month_name)
                filtered_occurrences = [
                    o for o in occurrences if o.get("month") == month_idx
                ]

            count_label = (
                f"**{len(filtered_occurrences)}** sightings for **{selected_month_name}**"
                if selected_month_name != "All Year"
                else f"**{len(occurrences)}** total recorded global sightings"
            )
            if filtered_occurrences:
                st.success(f"Showing {count_label}")
            else:
                st.warning(
                    f"No recorded sightings found for **{selected_month_name}** in this dataset."
                )

            from api_utils import build_heatmap, build_animated_map, build_marker_map
            from streamlit_folium import st_folium

            # ── Map type sub-tabs ────────────────────────────────────────────
            heat_tab, anim_tab, marker_tab = st.tabs(
                ["🔥 Heatmap", "🎞️ Animation", "📍 Markers"]
            )

            with heat_tab:
                m_heat = build_heatmap(filtered_occurrences, top_name)
                st_folium(m_heat, width=None, height=480, returned_objects=[], key=f"heat_{selected_month_name}")

            with anim_tab:
                if len(occurrences) > 0:
                    m_anim = build_animated_map(occurrences, top_name)
                    st_folium(m_anim, width=None, height=500, returned_objects=[], key="anim_map")
                else:
                    st.warning("Not enough data for animation.")

            with marker_tab:
                m_mark = build_marker_map(filtered_occurrences, top_name)
                st_folium(m_mark, width=None, height=480, returned_objects=[], key=f"mark_{selected_month_name}")

            # ── Year distribution chart ──────────────────────────────────────
            years = [o["year"] for o in filtered_occurrences if o["year"]]
            if years:
                import collections
                year_counts = collections.Counter(int(y) for y in years if str(y).isdigit())
                if year_counts:
                    st.markdown("**Sightings by year:**")
                    sorted_years = sorted(year_counts.keys())
                    counts = [year_counts[y] for y in sorted_years]
                    st.bar_chart(data={"Year": sorted_years, "Sightings": counts}, x="Year", y="Sightings", color="#40916c", height=220)

            # ── Near Me ─────────────────────────────────────────────────────
            st.divider()
            st.markdown("### 📍 Sightings Near Me")
            from api_utils import get_nearby_sightings, build_nearby_map
            radius_km = st.slider("Search radius (km)", 25, 500, 100, 25, key="near_me_radius")
            
            from streamlit_js_eval import get_geolocation
            geo = get_geolocation()
            user_lat = user_lon = None
            if geo and "coords" in geo:
                user_lat, user_lon = geo["coords"]["latitude"], geo["coords"]["longitude"]
                st.success(f"📍 Location acquired: ({user_lat:.4f}, {user_lon:.4f})")

            if user_lat is None:
                location_query = st.text_input("City / place name fallback", placeholder="e.g. Mumbai...")
                if location_query:
                    from api_utils import geocode_location
                    coords = geocode_location(location_query)
                    if coords: user_lat, user_lon = coords

            if user_lat is not None and user_lon is not None:
                nearby = get_nearby_sightings(occurrences, user_lat, user_lon, radius_km)
                if nearby:
                    m_near = build_nearby_map(nearby, user_lat, user_lon, top_name)
                    st_folium(m_near, width=None, height=420, returned_objects=[], key="near_map")
                else:
                    st.warning("No nearby sightings found.")
        else:
            st.warning("No iNaturalist occurrence data found.")

else:
    # ── Landing state ─────────────────────────────────────────────────────────
    st.markdown("""
    <div class="upload-area">
      <div style="font-size:3rem;">🦜</div>
      <h3 style="color:#1b4332;">Upload a Bird Photo to Get Started</h3>
      <p style="color:#4b5563;">The AI will identify the species from 25 common Indian birds</p>
    </div>
    """, unsafe_allow_html=True)

    # Sample species grid
    st.markdown("### 🌟 Species in the Database")
    cols = st.columns(5)
    items = list(SPECIES_DATA.items())
    for i, (name, sp) in enumerate(items):
        with cols[i % 5]:
            iucn_code = sp.get("iucn_status", "NE")
            cfg = IUCN_CONFIG.get(iucn_code, IUCN_CONFIG["NE"])
            st.markdown(
                f"""
                <div style="background:white;border-radius:10px;padding:0.8rem;
                            margin-bottom:0.6rem;box-shadow:0 1px 4px rgba(0,0,0,0.08);
                            border-top:3px solid {cfg['color']};">
                  <div style="font-weight:600;font-size:0.82rem;color:#1b4332;">{name}</div>
                  <div style="font-size:0.72rem;color:#6b7280;font-style:italic;">{sp['scientific_name']}</div>
                  <div style="margin-top:0.4rem;">
                    <span style="background:{cfg['color']};color:{cfg['text']};
                                 padding:1px 6px;border-radius:8px;font-size:0.7rem;
                                 font-weight:700;">{iucn_code}</span>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

# ── Footer ─────────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    "<div style='text-align:center;color:#9ca3af;font-size:0.8rem;'>"
    "Built with ❤️ for bird conservation awareness by Pranav and Pranavi · "
    "Data: iNaturalist · Status: IUCN Red List · Images: Kaggle 25 Indian Birds Dataset"
    "</div>",
    unsafe_allow_html=True,
)
