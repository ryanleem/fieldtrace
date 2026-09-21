from sqlalchemy import text
from app.db.session import get_engine
from app.models.vision import SessionImage, VisualFinding, AggregatedVisualFinding


def initialize_vision(engine=None):
    with (engine or get_engine()).begin() as connection:
        connection.execute(text('SELECT pg_advisory_xact_lock(41088003)'))
        for model in (SessionImage, VisualFinding, AggregatedVisualFinding):
            model.__table__.create(connection, checkfirst=True)


if __name__ == '__main__':
    initialize_vision()
