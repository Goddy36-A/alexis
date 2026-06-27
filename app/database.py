import sqlite3
from flask import g

def get_db(app=None):
    from flask import current_app
    _app = app or current_app
    if 'db' not in g:
        g.db = sqlite3.connect(_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'user',
    reputation INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    url TEXT,
    source TEXT,
    submitted_by INTEGER REFERENCES users(id),
    nlp_score REAL DEFAULT 0.0,
    nlp_label TEXT DEFAULT 'unverified',
    community_score REAL DEFAULT 0.0,
    final_verdict TEXT DEFAULT 'pending',
    vote_count INTEGER DEFAULT 0,
    flag_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER REFERENCES articles(id),
    user_id INTEGER REFERENCES users(id),
    vote TEXT NOT NULL,
    confidence INTEGER DEFAULT 3,
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(article_id, user_id)
);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER REFERENCES articles(id),
    user_id INTEGER REFERENCES users(id),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS expert_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER REFERENCES articles(id),
    reviewer_id INTEGER REFERENCES users(id),
    verdict TEXT NOT NULL,
    explanation TEXT,
    evidence_links TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS badges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    badge_name TEXT NOT NULL,
    awarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL,
    target_type TEXT,
    target_id INTEGER,
    detail TEXT,
    ip_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

def init_db(app):
    with app.app_context():
        db = sqlite3.connect(app.config['DATABASE'])
        db.executescript(SCHEMA)
        db.commit()
        db.close()
    app.teardown_appcontext(close_db)

def log_action(db, user_id, action, target_type=None, target_id=None, detail=None):
    """Write an entry to the audit log."""
    from flask import request as flask_request
    try:
        ip = flask_request.remote_addr
    except Exception:
        ip = None
    db.execute(
        'INSERT INTO audit_log (user_id, action, target_type, target_id, detail, ip_address) VALUES (?,?,?,?,?,?)',
        (user_id, action, target_type, target_id, detail, ip)
    )

