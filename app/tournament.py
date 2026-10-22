"""Opt-in daily score competition. No entry charge, reward or settlement writes."""
from datetime import datetime, timedelta
import time

from fastapi import APIRouter, Request, Response

from . import orbit, spin

router = APIRouter(prefix='/api/tournament', tags=['daily tournament'])
ROUND_LIMIT = 10


def open_db():
    db = orbit.open_db()
    db.execute('''CREATE TABLE IF NOT EXISTS tournament_entries (
        day TEXT NOT NULL, account_id TEXT NOT NULL REFERENCES accounts(id),
        joined_at REAL NOT NULL, PRIMARY KEY(day, account_id))''')
    db.execute('CREATE INDEX IF NOT EXISTS ix_orbit_tournament ON orbit_rounds(account_id,created_at)')
    return db


def event_window(stamp):
    start = datetime.fromtimestamp(stamp, spin.TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return start.date().isoformat(), start.timestamp(), (start + timedelta(days=1)).timestamp()


def snapshot(db, aid, stamp):
    day, start, end = event_window(stamp)
    # Only completed rounds STARTED after joining count. Never reveal future cards.
    # Rank multipliers are read from the existing authoritative paytable.
    points_case = 'CASE r.tier ' + ' '.join(
        f'WHEN {rank} THEN {tier["multiplier"]}' for rank, tier in orbit.CELEBRATIONS.items()) + ' ELSE 0 END'
    rows = db.execute(f'''
        WITH eligible AS (
          SELECT e.account_id, r.id, {points_case} AS points,
            ROW_NUMBER() OVER (PARTITION BY e.account_id ORDER BY r.created_at,r.id) AS n
          FROM tournament_entries e JOIN orbit_rounds r ON r.account_id=e.account_id
          WHERE e.day=? AND r.created_at>=e.joined_at AND r.created_at>=?
            AND r.finished_at<? AND r.picked=3 AND r.rules_version>=?
        ), scores AS (
          SELECT account_id,COUNT(*) AS rounds,SUM(points) AS points
          FROM eligible WHERE n<=? GROUP BY account_id
        ), standings AS (
          SELECT e.account_id,a.display_name,COALESCE(s.rounds,0) AS rounds,
            COALESCE(s.points,0) AS points,e.joined_at
          FROM tournament_entries e JOIN accounts a ON a.id=e.account_id
          LEFT JOIN scores s ON s.account_id=e.account_id WHERE e.day=?
        ), ranked AS (
          SELECT *,RANK() OVER (ORDER BY points DESC) AS position,
            ROW_NUMBER() OVER (ORDER BY points DESC,joined_at,account_id) AS rownum,
            COUNT(*) OVER () AS participants FROM standings
        ) SELECT * FROM ranked WHERE rownum<=20 OR account_id=? ORDER BY rownum
        ''', (day, start, end, orbit.RULES_VERSION, ROUND_LIMIT, day, aid)).fetchall()
    def public(row):
        return {'name': row['display_name'], 'points': row['points'], 'rounds': row['rounds'],
                'position': row['position'], 'is_you': row['account_id'] == aid}
    mine = next((public(r) for r in rows if r['account_id'] == aid), None)
    return {'event': {'id': day, 'title': 'Dragon Daily', 'ends_at': end,
                     'server_time': stamp, 'round_limit': ROUND_LIMIT, 'timezone': 'WIB',
                     'participants': rows[0]['participants'] if rows else 0},
            'you': mine, 'leaderboard': [public(r) for r in rows if r['rownum'] <= 20]}


@router.get('/state')
def state(request: Request, response: Response):
    db = open_db()
    try:
        acct = spin.account_from_session(request, db)
        db.execute('BEGIN')
        result = snapshot(db, acct['id'], time.time())
        response.headers['Cache-Control'] = 'no-store'
        return result
    finally:
        db.close()


@router.post('/join')
def join(request: Request, response: Response):
    spin.guard_write(request)
    db = open_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        acct = spin.account_from_session(request, db)
        stamp = time.time()
        day, _, _ = event_window(stamp)
        # Repeated taps/network retries retain the original entry window.
        db.execute('INSERT OR IGNORE INTO tournament_entries VALUES(?,?,?)', (day, acct['id'], stamp))
        result = snapshot(db, acct['id'], stamp)
        db.commit()
        response.headers['Cache-Control'] = 'no-store'
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
