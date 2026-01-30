CREATE TABLE IF NOT EXISTS link_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    child_key TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    token_salt TEXT NOT NULL,
    token_fingerprint TEXT NOT NULL UNIQUE,
    otp_hash TEXT NOT NULL,
    otp_salt TEXT NOT NULL,
    otp_fingerprint TEXT NOT NULL UNIQUE,
    issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP,
    revoked_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS child_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    child_key TEXT NOT NULL,
    line_user_id TEXT NOT NULL,
    linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(child_key, line_user_id)
);

CREATE INDEX IF NOT EXISTS idx_link_issues_child_key ON link_issues(child_key);
