#!/usr/bin/env python3
"""Compare rgb, depth, masks folders: frame counts, filename overlap, image dimensions.
Usage: python analyze_rgb_depth_masks.py [scene_dir]
Default scene_dir: parametric_data/surgery (relative to script dir).
"""
import os
import sys

def main():
    if len(sys.argv) > 1:
        base = os.path.abspath(sys.argv[1])
    else:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "surgery")
    rgb_dir = os.path.join(base, "rgb")
    depth_dir = os.path.join(base, "depth")
    masks_dir = os.path.join(base, "masks")

    def get_stems(d):
        if not os.path.isdir(d):
            return set()
        return set(os.path.splitext(f)[0] for f in os.listdir(d) if f.lower().endswith(".png"))

    rgb_stems = get_stems(rgb_dir)
    depth_stems = get_stems(depth_dir)
    masks_stems = get_stems(masks_dir)

    print("=== Frame counts ===")
    print(f"  rgb:   {len(rgb_stems)}")
    print(f"  depth: {len(depth_stems)}")
    print(f"  masks: {len(masks_stems)}")

    print("\n=== Filename overlap (using rgb as reference) ===")
    in_rgb_not_depth = rgb_stems - depth_stems
    in_rgb_not_masks = rgb_stems - masks_stems
    in_depth_not_rgb = depth_stems - rgb_stems
    in_masks_not_rgb = masks_stems - rgb_stems
    all_three = rgb_stems & depth_stems & masks_stems
    print(f"  Frames in all three (rgb & depth & masks): {len(all_three)}")
    print(f"  In rgb but missing in depth: {len(in_rgb_not_depth)}")
    if in_rgb_not_depth and len(in_rgb_not_depth) <= 20:
        print(f"    Examples: {sorted(in_rgb_not_depth)[:20]}")
    elif in_rgb_not_depth:
        print(f"    Examples: {sorted(in_rgb_not_depth)[:10]} ... {sorted(in_rgb_not_depth)[-5:]}")
    print(f"  In rgb but missing in masks: {len(in_rgb_not_masks)}")
    if in_rgb_not_masks and len(in_rgb_not_masks) <= 20:
        print(f"    Examples: {sorted(in_rgb_not_masks)[:20]}")
    elif in_rgb_not_masks:
        print(f"    Examples: {sorted(in_rgb_not_masks)[:10]} ... {sorted(in_rgb_not_masks)[-5:]}")
    print(f"  In depth but not in rgb: {len(in_depth_not_rgb)}")
    print(f"  In masks but not in rgb: {len(in_masks_not_rgb)}")

    print("\n=== Image dimensions (first frame present in all three) ===")
    try:
        import cv2
    except ImportError:
        print("  (install opencv-python to check dimensions)")
        return
    sample = next(iter(all_three), None)
    if not sample:
        print("  No frame common to all three folders.")
        return
    for name, d in [("rgb", rgb_dir), ("depth", depth_dir), ("masks", masks_dir)]:
        path = os.path.join(d, sample + ".png")
        if os.path.isfile(path):
            img = cv2.imread(path, -1)
            if img is not None:
                h, w = img.shape[:2]
                ch = img.shape[2] if len(img.shape) == 3 else 1
                print(f"  {name}: {w} x {h}  channels={ch}")
            else:
                print(f"  {name}: failed to read")
        else:
            print(f"  {name}: file not found")
    # Check a few more frames for consistent dimensions
    stems_list = sorted(all_three)
    if len(stems_list) > 5:
        print("\n=== Dimension consistency (sample of 5 frames) ===")
        for stem in stems_list[:2] + [stems_list[len(stems_list)//2]] + stems_list[-2:]:
            dims = {}
            for name, d in [("rgb", rgb_dir), ("depth", depth_dir), ("masks", masks_dir)]:
                path = os.path.join(d, stem + ".png")
                img = cv2.imread(path, -1)
                if img is not None:
                    dims[name] = (img.shape[1], img.shape[0])
            if len(dims) == 3:
                same = len(set(dims.values())) == 1
                print(f"  {stem}: rgb{dims.get('rgb')} depth{dims.get('depth')} masks{dims.get('masks')}  same={same}")

    # Discrepancy summary
    print("\n=== DISCREPANCY SUMMARY ===")
    issues = []
    if len(rgb_stems) != len(depth_stems) or len(rgb_stems) != len(masks_stems):
        issues.append(f"Frame count mismatch: rgb={len(rgb_stems)} depth={len(depth_stems)} masks={len(masks_stems)}")
    if in_rgb_not_depth or in_rgb_not_masks:
        issues.append(f"Missing correspondences: {len(in_rgb_not_depth)} rgb frames without depth, {len(in_rgb_not_masks)} without mask")
    sample_stem = next(iter(all_three), None) if all_three else None
    if sample_stem and os.path.isfile(os.path.join(rgb_dir, sample_stem + ".png")):
        try:
            import cv2
            r = cv2.imread(os.path.join(rgb_dir, sample_stem + ".png"))
            d = cv2.imread(os.path.join(depth_dir, sample_stem + ".png"), -1)
            m = cv2.imread(os.path.join(masks_dir, sample_stem + ".png"), -1)
            if r is not None and d is not None and m is not None:
                rw, rh = r.shape[1], r.shape[0]
                dw, dh = d.shape[1], d.shape[0]
                mw, mh = m.shape[1], m.shape[0]
                if (rw, rh) != (dw, dh) or (rw, rh) != (mw, mh):
                    issues.append(f"Resolution mismatch: rgb {rw}x{rh}  depth {dw}x{dh}  masks {mw}x{mh}")
        except Exception:
            pass
    if issues:
        for i in issues:
            print(f"  - {i}")
        print("  -> Consider aligning frame sets and/or resizing (e.g. mask to depth size) before use.")
    else:
        print("  No major discrepancies detected.")

if __name__ == "__main__":
    main()
