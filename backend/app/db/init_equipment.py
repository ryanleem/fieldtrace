import json

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import ROOT
from app.db.session import get_engine
from app.models.equipment import Equipment, EquipmentSession


def initialize_equipment(engine=None):
    engine = engine or get_engine()
    catalog = json.loads((ROOT / "data/equipment_catalog.json").read_text(encoding="utf-8"))
    with engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(41088002)"))
        Equipment.__table__.create(connection, checkfirst=True)
        EquipmentSession.__table__.create(connection, checkfirst=True)
        with Session(bind=connection) as session:
            for entry in catalog["equipment"]:
                existing = session.get(Equipment, entry["id"])
                if existing is None:
                    session.add(Equipment(**entry))
                else:
                    # Seed is idempotent; do not silently change confirmed catalog identities.
                    for key, value in entry.items():
                        if getattr(existing, key) != value:
                            raise ValueError(f"Catalog drift for {entry['id']}.{key}; migrate explicitly")
            session.flush()


if __name__ == "__main__":
    initialize_equipment()
    print("Step 2 catalog and session schema initialized")
