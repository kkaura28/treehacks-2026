import cv2
import csv
import numpy as np

def read_video_frames(video_path):
    cap = cv2.VideoCapture(video_path)
    frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
    cap.release()
    return frames

def init_tracking_point(x, y):
    # Prepare as numpy float32 for LK
    return np.array([[x, y]], dtype=np.float32)

def track_point_lk(frames, init_pt):
    # Parameters for Lucas-Kanade optical flow
    lk_params = dict(winSize=(15, 15),
                     maxLevel=3,
                     criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))

    # Prepare initial point
    prev_pts = init_pt.copy()
    prev_gray = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)

    tracked_positions = [(0, float(prev_pts[0][0]), float(prev_pts[0][1]))]

    for i in range(1, len(frames)):
        frame_gray = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
        
        next_pts, status, err = cv2.calcOpticalFlowPyrLK(prev_gray, frame_gray, prev_pts, None, **lk_params)

        if status[0][0] == 0:
            # Lost track — keep previous
            next_pts = prev_pts.copy()

        x, y = next_pts[0]
        tracked_positions.append((i, float(x), float(y)))

        prev_gray = frame_gray.copy()
        prev_pts = next_pts.copy()

    return tracked_positions

def save_to_csv(tracked_positions, out_csv="tracked_output.csv"):
    with open(out_csv, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["frame_idx", "x", "y"])
        writer.writerows(tracked_positions)
    print(f"Saved tracked coords to {out_csv}")

def main(video_path, init_x, init_y, out_csv="tracked_output.csv"):
    frames = read_video_frames(video_path)
    init_pt = init_tracking_point(init_x, init_y)
    tracked_positions = track_point_lk(frames, init_pt)
    save_to_csv(tracked_positions, out_csv)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True, help="Path to input video")
    parser.add_argument("--x", required=True, type=float, help="Initial x coordinate of point")
    parser.add_argument("--y", required=True, type=float, help="Initial y coordinate of point")
    parser.add_argument("--out", default="tracked_output.csv", help="Output CSV path")
    args = parser.parse_args()
    main(args.video, args.x, args.y, args.out)
