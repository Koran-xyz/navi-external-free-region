PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS cafe_tables (
  room_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  password_salt TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cafe_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_id TEXT NOT NULL,
  display_name TEXT NOT NULL,
  actor_type TEXT NOT NULL,
  body TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (room_id) REFERENCES cafe_tables(room_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_cafe_tables_expires
ON cafe_tables(expires_at);

CREATE INDEX IF NOT EXISTS idx_cafe_messages_room_id_id
ON cafe_messages(room_id, id);
