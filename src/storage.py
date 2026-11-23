import json
import sqlite3
from pathlib import Path

SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, manifest TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS comments (run_id TEXT NOT NULL REFERENCES runs(id), id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(run_id,id));
CREATE TABLE IF NOT EXISTS claims (run_id TEXT NOT NULL REFERENCES runs(id), id TEXT NOT NULL, fingerprint TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(run_id,id));
CREATE TABLE IF NOT EXISTS evidence (run_id TEXT NOT NULL REFERENCES runs(id), id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(run_id,id));
CREATE TABLE IF NOT EXISTS reviews (seq INTEGER PRIMARY KEY AUTOINCREMENT, claim_id TEXT NOT NULL, fingerprint TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL);
'''


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def db_path(root):
    return Path(root) / 'data/results/observatory.sqlite'


def connect(root, readonly=False):
    path = db_path(root)
    if readonly:
        connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        connection.executescript(SCHEMA)
    connection.row_factory = sqlite3.Row
    return connection


def apply_reviews(conn, claim):
    review = conn.execute('SELECT payload FROM reviews WHERE claim_id=? AND fingerprint=? ORDER BY seq DESC LIMIT 1', (claim['id'], claim['fingerprint'])).fetchone()
    if review:
        claim.update(json.loads(review['payload']))
    return claim


def save_run(root, manifest, comments, claims, evidence):
    with connect(root) as conn:
        conn.execute('INSERT INTO runs VALUES (?,?,?)', (manifest['id'], manifest['created_at'], encode(manifest)))
        for table, values in (('comments', comments), ('claims', claims), ('evidence', evidence)):
            for item in values:
                if table == 'claims':
                    apply_reviews(conn, item)
                    conn.execute('INSERT INTO claims VALUES (?,?,?,?)', (manifest['id'], item['id'], item['fingerprint'], encode(item)))
                else:
                    conn.execute(f'INSERT INTO {table} VALUES (?,?,?)', (manifest['id'], item['id'] if table == 'evidence' else item['uid'], encode(item)))


def snapshot(root, run_id=None):
    with connect(root, readonly=True) as conn:
        run = conn.execute('SELECT * FROM runs WHERE id=?', (run_id,)).fetchone() if run_id else conn.execute('SELECT * FROM runs ORDER BY rowid DESC LIMIT 1').fetchone()
        if not run:
            raise ValueError('尚無分析結果，請先執行 python run.py')
        result = {'manifest': json.loads(run['manifest'])}
        for table in ('comments', 'claims', 'evidence'):
            result[table] = [json.loads(r['payload']) for r in conn.execute(f'SELECT payload FROM {table} WHERE run_id=? ORDER BY rowid', (run['id'],))]
        return result


def list_runs(root):
    with connect(root, readonly=True) as conn:
        return [json.loads(r['manifest']) for r in conn.execute('SELECT manifest FROM runs ORDER BY rowid DESC LIMIT 100')]
