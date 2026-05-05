"""
model_utils.py — Inference helpers for the Bird ID app.

Supports two modes:
  1. Fine-tuned EfficientNet-B0 (bird_classifier.pth)  ← preferred
  2. CLIP zero-shot fallback (openai/clip-vit-base-patch32)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
import timm
from torchvision import transforms

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
MODEL_PATH = BASE_DIR / "bird_classifier.pth"
CLASS_JSON = BASE_DIR / "class_names.json"

# ── 25 Indian bird classes (canonical names matching dataset folders) ─────────
INDIAN_BIRD_CLASSES = [
    "Asian Green Bee-eater",
    "Asian Paradise-flycatcher",
    "Black-headed Ibis",
    "Black-hooded Oriole",
    "Brahminy Kite",
    "Changeable Hawk-Eagle",
    "Coppersmith Barbet",
    "Crested Kingfisher",
    "Crested Serpent Eagle",
    "Eurasian Hoopoe",
    "Grey-headed Fish Eagle",
    "Indian Golden Oriole",
    "Indian Peafowl",
    "Indian Pitta",
    "Indian Roller",
    "Malabar Whistling Thrush",
    "Purple Sunbird",
    "Red Junglefowl",
    "Red-wattled Lapwing",
    "Shikra",
    "Spotted Owlet",
    "White-throated Kingfisher",
    "White-throated Munia",
    "Woolly-necked Stork",
    "Yellow-footed Green Pigeon",
]

CLIP_PROMPTS = [f"a photo of a {cls}, an Indian bird" for cls in INDIAN_BIRD_CLASSES]

# ── EfficientNet transforms ───────────────────────────────────────────────────
_EFFNET_TF = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


# ─────────────────────────────────────────────────────────────────────────────
# Fine-tuned EfficientNet loader
# ─────────────────────────────────────────────────────────────────────────────
_effnet_model = None
_effnet_classes: list[str] = []


def _load_effnet():
    global _effnet_model, _effnet_classes
    if _effnet_model is not None:
        return True

    if not MODEL_PATH.exists():
        return False

    ckpt = torch.load(MODEL_PATH, map_location="cpu")
    _effnet_classes = ckpt.get("classes", INDIAN_BIRD_CLASSES)
    num_classes = ckpt.get("num_classes", len(_effnet_classes))

    import timm
    model = timm.create_model("efficientnet_b0", pretrained=False, num_classes=num_classes)
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    _effnet_model = model
    return True


def predict_effnet(image: Image.Image, top_k: int = 3) -> list[tuple[str, float]]:
    """Return top-k (class_name, probability) using fine-tuned EfficientNet."""
    if not _load_effnet():
        raise FileNotFoundError("bird_classifier.pth not found — run train_model.py first.")

    tensor = _EFFNET_TF(image).unsqueeze(0)
    with torch.no_grad():
        logits = _effnet_model(tensor)
        probs = F.softmax(logits, dim=1).squeeze(0).numpy()

    top_idx = np.argsort(probs)[::-1][:top_k]
    return [(_effnet_classes[i], float(probs[i])) for i in top_idx]


# ─────────────────────────────────────────────────────────────────────────────
# CLIP zero-shot fallback
# ─────────────────────────────────────────────────────────────────────────────
_clip_model = None
_clip_processor = None


def _load_clip():
    global _clip_model, _clip_processor
    if _clip_model is not None:
        return
    from transformers import CLIPModel, CLIPProcessor
    _clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32", use_fast=True)
    _clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
    _clip_model.eval()


def predict_clip(image: Image.Image, top_k: int = 3) -> list[tuple[str, float]]:
    """Return top-k (class_name, probability) using CLIP zero-shot."""
    _load_clip()

    inputs = _clip_processor(
        text=CLIP_PROMPTS,
        images=image,
        return_tensors="pt",
        padding=True,
    )
    with torch.no_grad():
        outputs = _clip_model(**inputs)
        logits = outputs.logits_per_image.squeeze(0)
        probs = F.softmax(logits, dim=0).numpy()

    top_idx = np.argsort(probs)[::-1][:top_k]
    return [(INDIAN_BIRD_CLASSES[i], float(probs[i])) for i in top_idx]


# ─────────────────────────────────────────────────────────────────────────────
# Unified predict — tries EfficientNet first, falls back to CLIP
# ─────────────────────────────────────────────────────────────────────────────
def predict(image: Image.Image, top_k: int = 3) -> tuple[list[tuple[str, float]], str]:
    """
    Returns:
        predictions: list of (name, probability)
        backend:     'efficientnet' | 'clip'
    """
    if MODEL_PATH.exists():
        try:
            return predict_effnet(image, top_k), "efficientnet"
        except Exception:
            pass
    return predict_clip(image, top_k), "clip"
