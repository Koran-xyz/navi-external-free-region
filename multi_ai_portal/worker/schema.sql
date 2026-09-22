CREATE TABLE IF NOT EXISTS rooms (
  room_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  token_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_id TEXT NOT NULL,
  sender_name TEXT NOT NULL,
  sender_type TEXT NOT NULL,
  team_id TEXT,
  body TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (room_id) REFERENCES rooms(room_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_room_id_id
ON messages(room_id, id);

CREATE INDEX IF NOT EXISTS idx_rooms_expires_at
ON rooms(expires_at);
