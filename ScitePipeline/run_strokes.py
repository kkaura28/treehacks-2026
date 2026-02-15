"""
Run stroke segmentation on all video sessions and update Supabase.
"""
import json
import logging
from stroke_interpreter import segment_strokes
from config import get_supabase

logging.basicConfig(level=logging.INFO, format="%(message)s")

sb = get_supabase()

# Steps to segment: events with video_path and surgical action nodes
SURGICAL_NODES = {"incision", "loculation_breakdown", "drainage_expression"}

# Get all events with video paths
res = sb.table("observed_events").select("id, node_id, metadata, procedure_run_id").order("timestamp").execute()
events = [e for e in res.data if e["metadata"].get("video_path") and e["node_id"] in SURGICAL_NODES]

print(f"Found {len(events)} events to segment\n")

# Get procedure name
proc_name = "Incision and Drainage of Abscess"

# Get node names
nodes_res = sb.table("nodes").select("id, name").eq("procedure_id", "incision_drainage_abscess").execute()
node_names = {n["id"]: n["name"] for n in nodes_res.data}

# For each event, figure out the end time (start of next event or +30s)
all_events_res = sb.table("observed_events").select("id, node_id, metadata, procedure_run_id").order("timestamp").execute()
events_by_run = {}
for e in all_events_res.data:
    run_id = e["procedure_run_id"]
    if run_id not in events_by_run:
        events_by_run[run_id] = []
    events_by_run[run_id].append(e)

for event in events:
    run_events = events_by_run.get(event["procedure_run_id"], [])
    ts = event["metadata"].get("timestamp_seconds", 0)
    step_name = node_names.get(event["node_id"], event["node_id"])
    video_path = event["metadata"]["video_path"]

    # Find end time: next event's timestamp or +30s
    end_seconds = ts + 30
    for i, re in enumerate(run_events):
        if re["id"] == event["id"] and i + 1 < len(run_events):
            next_ts = run_events[i + 1]["metadata"].get("timestamp_seconds")
            if next_ts:
                end_seconds = next_ts
            break

    print(f"{'='*60}")
    print(f"Event {event['id']}: {step_name}")
    print(f"  Video: {video_path}")
    print(f"  Window: {ts}s – {end_seconds}s")
    print(f"  Calling Gemini...")

    try:
        strokes = segment_strokes(
            video_path=video_path,
            procedure_name=proc_name,
            step_name=step_name,
            start_seconds=ts,
            end_seconds=end_seconds,
        )

        print(f"  Got {len(strokes)} strokes:")
        for s in strokes:
            print(f"    {s['timestamp_seconds']}s–{s['end_seconds']}s | {s['stroke_type']} ({s['instrument']}): {s['description']}")

        # Update metadata
        meta = {**event["metadata"], "strokes": strokes}
        sb.table("observed_events").update({"metadata": meta}).eq("id", event["id"]).execute()
        print(f"  ✓ Saved to DB")

    except Exception as e:
        print(f"  ✗ Error: {e}")

    print()

print("Done!")

