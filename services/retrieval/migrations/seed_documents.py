# seed_documents.py - simple seeder for documents table (requires PG_CONN env)
import os, psycopg2, json
conn_str = os.getenv('PG_CONN','')
if not conn_str:
    print('PG_CONN not set; skipping seed')
else:
    docs = [
        ('Architecture Notes','Design details about agent architecture...'),
        ('RAG Design','RAG retrieval design and tips...'),
    ]
    conn = psycopg2.connect(conn_str)
    cur = conn.cursor()
    for t,txt in docs:
        cur.execute('INSERT INTO documents (title,text) VALUES (%s,%s)', (t,txt))
    conn.commit(); conn.close()
    print('seeded documents')
