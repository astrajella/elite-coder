#!/usr/bin/env python3
import os, glob, psycopg2
pg = os.getenv('PG_CONN','')
if not pg:
    print('PG_CONN not set. Exiting')
    exit(1)
conn = psycopg2.connect(pg); cur = conn.cursor()
for f in sorted(glob.glob('services/retrieval/migrations/*.sql')):
    print('Applying', f)
    cur.execute(open(f).read())
conn.commit(); conn.close()
print('Migrations applied')
