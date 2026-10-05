"""What flowed through central-bus, from the bronze buckets, via DuckDB.
Views: archive (raw/), quarantine (processing-failed/, with reason), bronze (both, with status).
Run: task query [-- "<sql>"]"""
import sys

from harness import duck

DEFAULT = """
SELECT status, reason, source, detail_type, count(*) AS events, min(time) AS first_seen, max(time) AS last_seen
FROM bronze GROUP BY ALL ORDER BY 1, 2, 3, 4
"""

con = duck()
sql = " ".join(sys.argv[1:]) or DEFAULT
print(con.sql(sql))
