#!/usr/bin/env bash
# setup.sh — One-shot environment setup for Indian Bird Identifier
# Usage: bash setup.sh [--with-dataset]
# Requires: Python 3.9+, pip, (optionally) Kaggle API key at ~/.kaggle/kaggle.json

set -e

echo "=========================================="
echo "  Indian Bird Identifier — Setup Script"
echo "=========================================="

# ── 1. Install Python dependencies ────────────────────────────────────────────
echo ""
echo "1/4  Installing Python packages…"
pip3 install -q -r requirements.txt

# ── 2. Create cache directory ──────────────────────────────────────────────────
echo "2/4  Preparing cache directory…"
mkdir -p cache

# ── 3. (Optional) Download dataset from Kaggle ───────────────────────────────
if [[ "$1" == "--with-dataset" ]]; then
  echo "3/4  Downloading dataset from Kaggle…"
  if [ ! -f ~/.kaggle/kaggle.json ]; then
    echo "ERROR: ~/.kaggle/kaggle.json not found."
    echo "  1. Go to https://www.kaggle.com/settings → API → Create New Token"
    echo "  2. Move the downloaded kaggle.json to ~/.kaggle/kaggle.json"
    exit 1
  fi
  chmod 600 ~/.kaggle/kaggle.json
  kaggle datasets download -d arjunbasandrai/25-indian-bird-species-with-226k-images -p ./dataset --unzip
  echo "  Dataset downloaded to ./dataset/"
else
  echo "3/4  Skipping dataset download (pass --with-dataset to download from Kaggle)"
fi

# ── 4. Train model (if dataset present) ──────────────────────────────────────
if [ -d "./dataset" ] && [ ! -f "bird_classifier.pth" ]; then
  echo "4/4  Training EfficientNet-B0 (this may take 20-60 min on CPU, ~5 min on GPU)…"
  python3 train_model.py --data_dir ./dataset --epochs 20 --batch_size 32
else
  if [ -f "bird_classifier.pth" ]; then
    echo "4/4  bird_classifier.pth found — skipping training."
  else
    echo "4/4  No dataset found — app will use CLIP zero-shot fallback."
  fi
fi

echo ""
echo "=========================================="
echo "  Setup complete! Run the app with:"
echo "    python3 -m streamlit run app.py"
echo "=========================================="
