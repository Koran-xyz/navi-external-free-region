PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS portal_users (
  username TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  actor_type TEXT NOT NULL,
  team_id TEXT,
  password_salt TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  username TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  FOREIGN KEY (username) REFERENCES portal_users(username) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS rooms (
  room_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  owner_username TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  FOREIGN KEY (owner_username) REFERENCES portal_users(username)
);

CREATE TABLE IF NOT EXISTS room_members (
  room_id TEXT NOT NULL,
  username TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'member',
  joined_at TEXT NOT NULL,
  PRIMARY KEY (room_id, username),
  FOREIGN KEY (room_id) REFERENCES rooms(room_id) ON DELETE CASCADE,
  FOREIGN KEY (username) REFERENCES portal_users(username) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS room_invites (
  invite_hash TEXT PRIMARY KEY,
  room_id TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  used_by TEXT,
  used_at TEXT,
  FOREIGN KEY (room_id) REFERENCES rooms(room_id) ON DELETE CASCADE,
  FOREIGN KEY (created_by) REFERENCES portal_users(username)
);

CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_id TEXT NOT NULL,
  username TEXT NOT NULL,
  body TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (room_id) REFERENCES rooms(room_id) ON DELETE CASCADE,
  FOREIGN KEY (username) REFERENCES portal_users(username)
);

CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_rooms_expires ON rooms(expires_at);
CREATE INDEX IF NOT EXISTS idx_room_members_username ON room_members(username);
CREATE INDEX IF NOT EXISTS idx_messages_room_id_id ON messages(room_id, id);
CREATE INDEX IF NOT EXISTS idx_invites_room ON room_invites(room_id);
