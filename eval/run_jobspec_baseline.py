"""Writes regex-baseline predictions for a request set: python -m eval.run_jobspec_baseline REQUESTS OUT_PREDS"""
import json
import sys

from jobspec.baseline import parse

src, out = sys.argv[1], sys.argv[2]
with open(src, encoding="utf-8") as f, open(out, "w", encoding="utf-8", newline="\n") as g:
    for line in f:
        row = json.loads(line)
        g.write(json.dumps({"id": row["id"], "outputs": [json.dumps(parse(row["request"]))]}) + "\n")
