# create_spider_catalog_tables.py
import psycopg2

DSN = "postgresql://nisseya:password123@localhost:5432/benchmark_db"

DDL = """
BEGIN;

CREATE TABLE IF NOT EXISTS spider_databases (
  db_id TEXT PRIMARY KEY,
  table_names JSONB NOT NULL,
  table_names_original JSONB NOT NULL,
  raw JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS spider_tables (
  db_id TEXT NOT NULL REFERENCES spider_databases(db_id) ON DELETE CASCADE,
  table_id INT NOT NULL,
  name TEXT NOT NULL,
  name_original TEXT NOT NULL,
  PRIMARY KEY (db_id, table_id)
);

CREATE TABLE IF NOT EXISTS spider_columns (
  db_id TEXT NOT NULL REFERENCES spider_databases(db_id) ON DELETE CASCADE,
  column_id INT NOT NULL,
  table_id INT NULL,                 -- NULL for the pseudo "*" row
  name TEXT NOT NULL,
  name_original TEXT NOT NULL,
  col_type TEXT NOT NULL,
  PRIMARY KEY (db_id, column_id),
  FOREIGN KEY (db_id, table_id) REFERENCES spider_tables(db_id, table_id)
    DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE IF NOT EXISTS spider_primary_keys (
  db_id TEXT NOT NULL REFERENCES spider_databases(db_id) ON DELETE CASCADE,
  column_id INT NOT NULL,
  PRIMARY KEY (db_id, column_id),
  FOREIGN KEY (db_id, column_id) REFERENCES spider_columns(db_id, column_id)
    DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE IF NOT EXISTS spider_foreign_keys (
  db_id TEXT NOT NULL REFERENCES spider_databases(db_id) ON DELETE CASCADE,
  from_column_id INT NOT NULL,
  to_column_id INT NOT NULL,
  PRIMARY KEY (db_id, from_column_id, to_column_id),
  FOREIGN KEY (db_id, from_column_id) REFERENCES spider_columns(db_id, column_id)
    DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (db_id, to_column_id) REFERENCES spider_columns(db_id, column_id)
    DEFERRABLE INITIALLY DEFERRED
);

-- Helpful indexes (optional but useful)
CREATE INDEX IF NOT EXISTS spider_tables_dbid_idx ON spider_tables (db_id);
CREATE INDEX IF NOT EXISTS spider_columns_dbid_idx ON spider_columns (db_id);
CREATE INDEX IF NOT EXISTS spider_columns_table_idx ON spider_columns (db_id, table_id);
CREATE INDEX IF NOT EXISTS spider_fk_dbid_idx ON spider_foreign_keys (db_id);

COMMIT;
"""

def main():
    conn = psycopg2.connect(dsn=DSN)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(DDL)
        print("✅ Spider catalog tables created/verified.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
