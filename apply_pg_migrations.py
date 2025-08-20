#!/usr/bin/env python3
import os
import glob
import psycopg2

pg = os.getenv('PG_CONN', '')
if not pg:
    print('PG_CONN not set. Exiting')
    exit(1)

conn = psycopg2.connect(pg)
cur = conn.cursor()

for f in sorted(glob.glob('services/retrieval/migrations/*.sql')):
    print('Applying', f)
    with open(f) as sql_file:
        cur.execute(sql_file.read())

conn.commit()
conn.close()

print('Migrations applied')
