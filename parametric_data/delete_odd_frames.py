#!/usr/bin/env python3
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
result_path = os.path.join(script_dir, "delete_odd_result.txt")
d = os.path.join(script_dir, "surgery", "new_visualization", "0")

with open(result_path, "w") as log:
    if not os.path.isdir(d):
        log.write("Directory not found: " + d + "\n")
        sys.exit(1)
    files = sorted(f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f)))
    log.write("Total files: " + str(len(files)) + "\n")
    deleted = 0
    for f in files:
        base, ext = os.path.splitext(f)
        if base.isdigit() and int(base) % 2 == 1:
            path = os.path.join(d, f)
            try:
                os.remove(path)
                deleted += 1
            except Exception as e:
                log.write("Error " + str(e) + " " + path + "\n")
    remaining = len(os.listdir(d))
    msg = "Deleted %d odd-numbered frames. Remaining: %d" % (deleted, remaining)
    log.write(msg + "\n")
print(msg)
