"""Turn unittest failures into GitHub annotations, so they are readable without opening the logs."""
import re
import sys

text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
blocks = re.split(r"^={50,}$", text, flags=re.M)[1:]
for block in blocks:
    block = re.split(r"^-{50,}\nRan \d+ tests?", block, flags=re.M)[0].strip()
    title, _, body = block.partition("\n")
    msg = body.strip("-\n ")[-4000:]
    msg = msg.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    title = title.replace("%", "%25").replace(":", "%3A").replace(",", "%2C")
    print(f"::error title={title}::{msg}")
