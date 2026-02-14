import sys
import os

# Add Depth-Anything-3 src to Python path so we can import it without pip install -e
DA3_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'Depth-Anything-3', 'src'))
sys.path.insert(0, DA3_SRC)

import torch
import numpy as np
import matplotlib.pyplot as plt
from depth_anything_3.api import DepthAnything3


# ---- Repo root (two levels up from analysis/src/) ----
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# ---- Hyperparameters (paths relative to repo root) ----
input_path = "analysis/data/depth/begreen-vboardmaster-office-5.jpg"
output_path = "analysis/outputs/depth/begreen-vboardmaster-office-5.png"
model_name = "depth-anything/DA3-SMALL"
# --------------------------

input_path = os.path.join(ROOT, input_path)
output_path = os.path.join(ROOT, output_path)
os.makedirs(os.path.dirname(output_path), exist_ok=True)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

print(f"Loading model: {model_name} ...")
model = DepthAnything3.from_pretrained(model_name)
model = model.to(device=device)

print(f"Running inference on: {input_path}")
prediction = model.inference([input_path])

# prediction.depth is [N, H, W] float32
depth = prediction.depth[0]

# Save as a colormapped image
plt.imsave(output_path, depth, cmap="inferno")
print(f"Depth map saved to: {output_path}")
