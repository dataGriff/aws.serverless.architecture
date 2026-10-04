"""What flowed through central-bus, from the S3 archive, via DuckDB. Run: task query [-- "<sql over view archive>"]"""
import sys

from harness import duck

DEFAULT = """
SELECT source, detail_type, count(*) AS events, min(time) AS first_seen, max(time) AS last_seen
FROM archive GROUP BY ALL ORDER BY 1, 2
"""

con = duck()
sql = " ".join(sys.argv[1:]) or DEFAULT
rel = con.sql(sql)
print(rel)
