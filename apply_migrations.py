#!/usr/bin/env python3
# convenience script to apply SQL migrations to Postgres (requires PG_CONN env var)
import os, psycopg2, glob
pg = os.getenv('PG_CONN','')
if not pg:
    print('PG_CONN not set. Exiting.')
    exit(1)
conn = psycopg2.connect(pg); cur = conn.cursor()
migs = glob.glob('services/retrieval/migrations/*.sql')
for m in sorted(migs):
    print('Applying', m)
    with open(m, 'r') as f:
        cur.execute(f.read())
conn.commit(); conn.close()
print('Migrations applied')
