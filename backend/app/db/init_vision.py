from sqlalchemy import text
from app.db.session import get_engine
from app.models.vision import SessionImage, VisualFinding, AggregatedVisualFinding


def initialize_vision(engine=None):
    with (engine or get_engine()).begin() as connection:
        connection.execute(text('SELECT pg_advisory_xact_lock(41088003)'))
        for model in (SessionImage, VisualFinding, AggregatedVisualFinding):
            model.__table__.create(connection, checkfirst=True)
    from app.db.migrate_image_fingerprints import migrate
    migrate(engine)
    from app.db.migrate_identification_evidence import migrate as migrate_identity
    migrate_identity(engine)


if __name__ == '__main__':
    initialize_vision()
