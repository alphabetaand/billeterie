import sqlite3

DB = "tickets_multi.db"  # event 2 database

conn = sqlite3.connect(DB)
cur = conn.cursor()

# Supprimer les anciens tickets s'ils existent
cur.execute("DELETE FROM tickets")

# Réinsérer 300 tickets vierges
cur.executemany(
    "INSERT INTO tickets (number, validated_at) VALUES (?, NULL)",
    [(i,) for i in range(1, 301)]
)

conn.commit()
conn.close()

print("✔ Event 2 réinitialisé à 300 tickets.")
