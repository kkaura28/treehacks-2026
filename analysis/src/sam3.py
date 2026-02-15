"""
sam3.py — Reusable helpers for SAM 3 (Segment Anything Model 3) image segmentation.

Usage:
    from analysis.src.sam3 import load_model, run_segmentation, visualize_and_save

    model, processor, device = load_model()
    image = Image.open("my_image.png").convert("RGB")
    results = run_segmentation(model, processor, image, "skin", device)
    visualize_and_save(image, results, "skin", "output_dir/")
"""

import os
import time

import torch
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from transformers import Sam3Model, Sam3Processor


# ──────────────────────────────────────────────────────────────────────
# Model loading
# ──────────────────────────────────────────────────────────────────────

def load_model(model_name: str = "facebook/sam3"):
    """Load SAM 3 model and processor onto GPU (or CPU fallback).

    Parameters
    ----------
    model_name : str
        Hugging Face model id (default ``"facebook/sam3"``).

    Returns
    -------
    model : Sam3Model
    processor : Sam3Processor
    device : str
        ``"cuda"`` or ``"cpu"``.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[sam3] Loading model: {model_name} on {device} ...")
    model = Sam3Model.from_pretrained(model_name).to(device)
    processor = Sam3Processor.from_pretrained(model_name)
    print("[sam3] Model and processor loaded successfully!")
    return model, processor, device


# ──────────────────────────────────────────────────────────────────────
# Inference
# ──────────────────────────────────────────────────────────────────────

def run_segmentation(model, processor, image, text_prompt: str, device: str,
                     threshold: float = 0.5):
    """Run SAM 3 text-prompted segmentation on a PIL image.

    Parameters
    ----------
    model : Sam3Model
    processor : Sam3Processor
    image : PIL.Image.Image
        Input RGB image.
    text_prompt : str
        Text description of objects to segment (e.g. ``"skin"``).
    device : str
        ``"cuda"`` or ``"cpu"``.
    threshold : float
        Confidence threshold for post-processing (default 0.5).

    Returns
    -------
    results : dict
        Post-processed results with keys ``'masks'`` and ``'scores'``.
    """
    inputs = processor(images=image, text=text_prompt, return_tensors="pt").to(device)
    print(f"[sam3] Running inference with prompt: '{text_prompt}' ...")
    t0 = time.time()
    with torch.no_grad():
        outputs = model(**inputs)
    results = processor.post_process_instance_segmentation(
        outputs, threshold=threshold, target_sizes=[image.size[::-1]]
    )[0]
    elapsed = time.time() - t0
    num_objects = len(results['masks'])
    scores = results['scores'].cpu().numpy()
    print(f"[sam3] Detected {num_objects} object(s) — scores: {scores}  ({elapsed:.3f}s)")
    return results


# ──────────────────────────────────────────────────────────────────────
# Visualisation & saving
# ──────────────────────────────────────────────────────────────────────

_COLORS = [
    (255, 0, 0),
    (0, 255, 0),
    (0, 0, 255),
    (255, 255, 0),
    (255, 0, 255),
]


def visualize_and_save(image, results, text_prompt: str, output_dir: str,
                       alpha: float = 0.45, show: bool = True):
    """Visualize masks, overlay on original image, and save all results to disk.

    Parameters
    ----------
    image : PIL.Image.Image
        Original RGB input image.
    results : dict
        Output of :func:`run_segmentation` (must contain ``'masks'`` and ``'scores'``).
    text_prompt : str
        Text prompt used for labelling the overlay.
    output_dir : str
        Directory to write overlay and mask PNGs.
    alpha : float
        Overlay transparency (default 0.45).
    show : bool
        If ``True`` (default), display the plots with ``plt.show()``.
        Set to ``False`` when running headless or in scripts.
    """
    masks = results['masks']
    scores = results['scores'].cpu().numpy()
    num_masks = len(masks)

    if num_masks == 0:
        print("[sam3] No masks detected.")
        return

    # --- Individual mask gallery ---
    fig, axes = plt.subplots(1, num_masks + 1, figsize=(6 * (num_masks + 1), 6))
    if num_masks + 1 == 1:
        axes = [axes]
    axes[0].imshow(image)
    axes[0].set_title("Original Image")
    axes[0].axis("off")
    for i, mask in enumerate(masks):
        mask_np = (mask.cpu().numpy() * 255).astype(np.uint8)
        axes[i + 1].imshow(mask_np, cmap="gray")
        axes[i + 1].set_title(f"Mask {i} — score {scores[i]:.3f}")
        axes[i + 1].axis("off")
    plt.tight_layout()
    if show:
        plt.show()
    plt.close(fig)

    # --- Colour overlay ---
    overlay = np.array(image).copy()
    for i, mask in enumerate(masks):
        mask_bool = mask.cpu().numpy().astype(bool)
        color = _COLORS[i % len(_COLORS)]
        for c in range(3):
            overlay[:, :, c] = np.where(
                mask_bool,
                overlay[:, :, c] * (1 - alpha) + color[c] * alpha,
                overlay[:, :, c],
            )
    fig2 = plt.figure(figsize=(10, 8))
    plt.imshow(overlay)
    plt.title(f"SAM 3 — '{text_prompt}' overlay ({num_masks} object(s))")
    plt.axis("off")
    if show:
        plt.show()
    plt.close(fig2)

    # --- Save to disk ---
    os.makedirs(output_dir, exist_ok=True)
    overlay_img = Image.fromarray(overlay.astype(np.uint8))
    overlay_path = os.path.join(output_dir, "overlay.png")
    overlay_img.save(overlay_path)
    print(f"[sam3] Saved overlay → {overlay_path}")
    for i, mask in enumerate(masks):
        mask_np = (mask.cpu().numpy() * 255).astype(np.uint8)
        mask_path = os.path.join(output_dir, f"mask_{i}.png")
        Image.fromarray(mask_np).save(mask_path)
        print(f"[sam3] Saved mask {i} → {mask_path}")
    print("[sam3] Done!")


# ──────────────────────────────────────────────────────────────────────
# Convenience: one-shot segmentation
# ──────────────────────────────────────────────────────────────────────

def segment_image(input_path: str, output_dir: str, text_prompt: str,
                  model_name: str = "facebook/sam3", threshold: float = 0.5,
                  alpha: float = 0.45, show: bool = True,
                  model=None, processor=None, device=None):
    """End-to-end convenience function: load model → open image → segment → save.

    If *model*, *processor*, and *device* are supplied they are reused
    (avoids reloading the model every call).

    Parameters
    ----------
    input_path : str
        Path to the input image.
    output_dir : str
        Directory to write outputs.
    text_prompt : str
        What to detect (e.g. ``"skin"``, ``"blade"``).
    model_name : str
        HF model id (only used when *model* is ``None``).
    threshold : float
        Confidence threshold.
    alpha : float
        Overlay transparency.
    show : bool
        Whether to call ``plt.show()``.
    model, processor, device
        Pre-loaded model artefacts (optional).

    Returns
    -------
    results : dict
        Post-processed segmentation results.
    model, processor, device
        The (potentially freshly-loaded) model artefacts, so the caller
        can reuse them.
    """
    if model is None or processor is None or device is None:
        model, processor, device = load_model(model_name)

    image = Image.open(input_path).convert("RGB")
    print(f"[sam3] Loaded image: {input_path}  size={image.size}")

    results = run_segmentation(model, processor, image, text_prompt, device, threshold)
    visualize_and_save(image, results, text_prompt, output_dir, alpha, show=show)

    return results, model, processor, device
