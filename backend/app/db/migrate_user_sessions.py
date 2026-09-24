"""Explicit, additive migration. Run once before deploying the authenticated backend."""
from sqlalchemy import text
from app.db.session import get_engine


def migrate(engine=None):
    with (engine or get_engine()).begin() as c:
        c.execute(text('SELECT pg_advisory_xact_lock(41088007)'))
        c.execute(text('ALTER TABLE equipment_sessions ADD COLUMN IF NOT EXISTS owner_user_id uuid'))
        c.execute(text('ALTER TABLE equipment_sessions ADD COLUMN IF NOT EXISTS session_name text'))
        # Keep legacy rows ownerless: never guess which authenticated user owns them.
        c.execute(text("""DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='owned_session_name'
                         AND conrelid='equipment_sessions'::regclass) THEN
            ALTER TABLE equipment_sessions ADD CONSTRAINT owned_session_name CHECK (
              owner_user_id IS NULL OR (session_name IS NOT NULL AND session_name=btrim(session_name)
                                        AND char_length(session_name) BETWEEN 1 AND 100));
          END IF;
        END $$"""))
        c.execute(text('CREATE INDEX IF NOT EXISTS ix_sessions_owner_updated ON equipment_sessions (owner_user_id, updated_at DESC, id DESC)'))
        # Touch the existing parent from child mutations, not from ordinary reads.
        c.execute(text("""CREATE OR REPLACE FUNCTION touch_equipment_session() RETURNS trigger AS $$
          BEGIN
            UPDATE equipment_sessions SET updated_at=clock_timestamp()
              WHERE id=CASE WHEN TG_OP='DELETE' THEN OLD.session_id ELSE NEW.session_id END;
            RETURN NULL;
          END; $$ LANGUAGE plpgsql"""))
        for table in ('session_images', 'visual_findings', 'aggregated_visual_findings',
                      'troubleshooting_sessions', 'troubleshooting_runs'):
            c.execute(text(f'DROP TRIGGER IF EXISTS touch_parent_session ON {table}'))
            c.execute(text(f'CREATE TRIGGER touch_parent_session AFTER INSERT OR UPDATE OR DELETE ON {table} '
                           'FOR EACH ROW EXECUTE FUNCTION touch_equipment_session()'))


if __name__ == '__main__':
    migrate()
    print('Session ownership migration complete; legacy rows remain ownerless and private.')
