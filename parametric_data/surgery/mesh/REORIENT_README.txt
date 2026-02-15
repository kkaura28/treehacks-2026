# Reoriented mesh variants (all 8)

Step 1 – Generate all 8 OBJs:
  cd /home/mnihar/Desktop/trees/treehacks-2026/parametric_data
  python3 reorient_mesh_all8.py surgery/mesh/scalpel_scaled.obj --out-dir surgery/mesh

Step 2 – Run FoundationPose with each mesh (use --mesh to pick one):
  python main.py --option 2 /path/to/parametric_data/surgery --mesh surgery/mesh/scalpel_scaled_X0Y0Z0.obj
  python main.py --option 2 /path/to/parametric_data/surgery --mesh surgery/mesh/scalpel_scaled_X0Y0Z90.obj
  ... etc.

File names and rotations (X, Y, Z in degrees; applied in that order):
  1. scalpel_scaled_X0Y0Z0.obj    = original (0, 0, 0)
  2. scalpel_scaled_X0Y0Z90.obj   = (0, 0, 90)
  3. scalpel_scaled_X0Y90Z0.obj   = (0, 90, 0)   <- blade Z -> X
  4. scalpel_scaled_X0Y90Z90.obj  = (0, 90, 90)
  5. scalpel_scaled_X90Y0Z0.obj   = (90, 0, 0)
  6. scalpel_scaled_X90Y0Z90.obj  = (90, 0, 90)
  7. scalpel_scaled_X90Y90Z0.obj  = (90, 90, 0)
  8. scalpel_scaled_X90Y90Z90.obj = (90, 90, 90)
