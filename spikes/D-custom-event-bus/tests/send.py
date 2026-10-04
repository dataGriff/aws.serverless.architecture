"""Publish the entries in a Classic-style events file to the Custom bus. Run: task send -- events/order-placed.json"""
import json
import sys

from harness import BUS_ARN, eb

entries = json.loads(open(sys.argv[1]).read())
r = eb.put_events(EventBusArn=BUS_ARN, Entries=[{"Source": e["Source"], "DetailType": e["DetailType"], "Detail": e["Detail"]} for e in entries])
print(json.dumps(r["Entries"], indent=2, default=str))
