"""
train_model.py - Fine-tune EfficientNet-B0 on 25 Indian Bird Species
Run this once to produce bird_classifier.pth

Usage:
  python train_model.py --data_dir ./dataset --epochs 20 --batch_size 32
"""

import os
import json
import argparse
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset, random_split
from torchvision import transforms
from PIL import Image
import timm
from tqdm import tqdm
import numpy as np


# ── Dataset ──────────────────────────────────────────────────────────────────
class BirdDataset(Dataset):
    """Loads images from a folder-per-class directory structure."""

    def __init__(self, root_dir: str, transform=None):
        self.root_dir = root_dir
        self.transform = transform
        self.samples: list[tuple[str, int]] = []
        self.classes: list[str] = []
        self.class_to_idx: dict[str, int] = {}

        # Discover class folders
        class_dirs = sorted(
            d for d in os.listdir(root_dir)
            if os.path.isdir(os.path.join(root_dir, d))
        )
        self.classes = class_dirs
        self.class_to_idx = {cls: i for i, cls in enumerate(class_dirs)}

        exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
        for cls in class_dirs:
            cls_path = os.path.join(root_dir, cls)
            for fname in os.listdir(cls_path):
                if os.path.splitext(fname)[1].lower() in exts:
                    self.samples.append(
                        (os.path.join(cls_path, fname), self.class_to_idx[cls])
                    )

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        img = Image.open(path).convert("RGB")
        if self.transform:
            img = self.transform(img)
        return img, label


# ── Transforms ───────────────────────────────────────────────────────────────
def get_transforms():
    train_tf = transforms.Compose([
        transforms.RandomResizedCrop(224, scale=(0.6, 1.0)),
        transforms.RandomHorizontalFlip(),
        transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.2, hue=0.1),
        transforms.RandomRotation(15),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    val_tf = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    return train_tf, val_tf


# ── Model ─────────────────────────────────────────────────────────────────────
def build_model(num_classes: int) -> nn.Module:
    model = timm.create_model(
        "efficientnet_b0",
        pretrained=True,
        num_classes=num_classes,
    )
    return model


# ── Training loop ────────────────────────────────────────────────────────────
def train_one_epoch(model, loader, criterion, optimizer, device):
    model.train()
    total_loss, correct, total = 0.0, 0, 0
    for imgs, labels in tqdm(loader, desc="  Train", leave=False):
        imgs, labels = imgs.to(device), labels.to(device)
        optimizer.zero_grad()
        outputs = model(imgs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * imgs.size(0)
        _, preds = outputs.max(1)
        correct += preds.eq(labels).sum().item()
        total += imgs.size(0)
    return total_loss / total, correct / total


@torch.no_grad()
def evaluate(model, loader, criterion, device):
    model.eval()
    total_loss, correct, total = 0.0, 0, 0
    for imgs, labels in tqdm(loader, desc="  Val  ", leave=False):
        imgs, labels = imgs.to(device), labels.to(device)
        outputs = model(imgs)
        loss = criterion(outputs, labels)
        total_loss += loss.item() * imgs.size(0)
        _, preds = outputs.max(1)
        correct += preds.eq(labels).sum().item()
        total += imgs.size(0)
    return total_loss / total, correct / total


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", default="./dataset", help="Root of dataset (class folders inside)")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--val_split", type=float, default=0.15)
    parser.add_argument("--output", default="bird_classifier.pth")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    train_tf, val_tf = get_transforms()

    # Load full dataset with train transforms, then split
    full_ds = BirdDataset(args.data_dir, transform=train_tf)
    num_classes = len(full_ds.classes)
    print(f"Classes ({num_classes}): {full_ds.classes}")

    val_size = int(len(full_ds) * args.val_split)
    train_size = len(full_ds) - val_size
    train_ds, val_ds_raw = random_split(
        full_ds, [train_size, val_size],
        generator=torch.Generator().manual_seed(42)
    )

    # Swap val transform
    val_ds_raw.dataset = BirdDataset(args.data_dir, transform=val_tf)

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=4, pin_memory=True)
    val_loader = DataLoader(val_ds_raw, batch_size=args.batch_size, shuffle=False, num_workers=4, pin_memory=True)

    model = build_model(num_classes).to(device)
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    optimizer = optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    best_val_acc = 0.0
    for epoch in range(1, args.epochs + 1):
        print(f"\nEpoch {epoch}/{args.epochs}")
        tr_loss, tr_acc = train_one_epoch(model, train_loader, criterion, optimizer, device)
        vl_loss, vl_acc = evaluate(model, val_loader, criterion, device)
        scheduler.step()
        print(f"  Train loss: {tr_loss:.4f}  acc: {tr_acc:.4f}")
        print(f"  Val   loss: {vl_loss:.4f}  acc: {vl_acc:.4f}")

        if vl_acc > best_val_acc:
            best_val_acc = vl_acc
            torch.save({
                "model_state": model.state_dict(),
                "classes": full_ds.classes,
                "class_to_idx": full_ds.class_to_idx,
                "num_classes": num_classes,
                "arch": "efficientnet_b0",
            }, args.output)
            print(f"  ✓ Saved best model (val_acc={best_val_acc:.4f})")

    print(f"\nTraining complete. Best val acc: {best_val_acc:.4f}")
    print(f"Model saved to: {args.output}")

    # Save class list for the app
    with open("class_names.json", "w") as f:
        json.dump(full_ds.classes, f, indent=2)
    print("class_names.json saved.")


if __name__ == "__main__":
    main()
