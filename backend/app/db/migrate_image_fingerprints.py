"""Additive, repeatable image retry protection; legacy files/rows are retained."""
from sqlalchemy import text
from app.db.session import get_engine

def migrate(engine=None):
    with (engine or get_engine()).begin() as c:
        c.execute(text('SELECT pg_advisory_xact_lock(41088008)'))
        c.execute(text('ALTER TABLE session_images ADD COLUMN IF NOT EXISTS content_sha256 text'))
        c.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS ix_session_image_hash ON session_images (session_id, content_sha256)'))

if __name__ == '__main__':
    migrate()
    print('Image fingerprint migration complete; existing images retained.')
