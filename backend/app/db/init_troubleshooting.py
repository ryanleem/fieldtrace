from sqlalchemy import text
from app.db.session import get_engine
from app.models.troubleshooting import TroubleshootingSession, TroubleshootingRun


def initialize_troubleshooting(engine=None):
    with (engine or get_engine()).begin() as connection:
        connection.execute(text('SELECT pg_advisory_xact_lock(41088004)'))
        for model in (TroubleshootingSession, TroubleshootingRun):
            model.__table__.create(connection, checkfirst=True)


if __name__ == '__main__':
    initialize_troubleshooting()
