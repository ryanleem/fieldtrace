"""Repeatable additive identity metadata; preserves all existing case data."""
from sqlalchemy import text
from app.db.session import get_engine

def migrate(engine=None):
    with (engine or get_engine()).begin() as c:
        c.execute(text('SELECT pg_advisory_xact_lock(41088009)'))
        c.execute(text("ALTER TABLE IF EXISTS equipment_sessions ADD COLUMN IF NOT EXISTS identification_evidence jsonb NOT NULL DEFAULT '{}'::jsonb"))
        # Nullable distinguishes legacy metadata; legacy nameplates remain selected.
        c.execute(text('ALTER TABLE IF EXISTS session_images ADD COLUMN IF NOT EXISTS use_for_identification boolean'))

if __name__ == '__main__':
    migrate()
    print('Identification evidence migration complete; existing data retained.')
