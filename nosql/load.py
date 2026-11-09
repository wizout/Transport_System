# створення баз і завантаження однакових даних у postgres і mongo
import json
import os
from pathlib import Path

import psycopg
from pymongo import MongoClient, ASCENDING
from pymongo.write_concern import WriteConcern

HERE = Path(__file__).resolve().parent
PG_USER = os.getenv("PGUSER", "postgres")
PG_PASSWORD = os.getenv("PGPASSWORD", "postgres")
PG_DB = "transport_bench"
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")


def pg_port():
    ports = [os.getenv("PGPORT")] if os.getenv("PGPORT") else ["5432", "5433", "5434", "5435"]
    for p in ports:
        try:
            psycopg.connect(host="localhost", port=p, user=PG_USER, password=PG_PASSWORD,
                            dbname="postgres", connect_timeout=3).close()
            return p
        except psycopg.Error:
            pass
    raise SystemExit("не вдалось підключитись до postgres")


def pg_connect(port, db=PG_DB, autocommit=False):
    return psycopg.connect(host="localhost", port=port, user=PG_USER, password=PG_PASSWORD,
                           dbname=db, autocommit=autocommit)


def mongo_db():
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
    client.admin.command("ping")
    return client["transport_bench"]


def trips_collection(db):
    # j=True - чекаємо запис в журнал на диск, як postgres чекає fsync при commit. інакше порівняння нечесне
    return db.get_collection("trips", write_concern=WriteConcern(w=1, j=True))


def load_postgres(port, d):
    with pg_connect(port, "postgres", autocommit=True) as c:
        c.execute(f"drop database if exists {PG_DB} with (force)")
        c.execute(f"create database {PG_DB}")

    with pg_connect(port, autocommit=True) as c:
        c.execute((HERE.parent / "docs" / "schema_init.sql").read_text(encoding="utf-8"))
        c.execute((HERE / "sql_archive.sql").read_text(encoding="utf-8"))

    with pg_connect(port) as c:
        with c.cursor() as cur:
            copy(cur, "depots(id, name, address, capacity)", d.depots)
            copy(cur, "vehicle_types(id, name, seats, standing)", d.vehicle_types)
            copy(cur, "vehicles(id, depot_id, type_id, plate, model, year_made)", d.vehicles)
            copy(cur, "drivers(id, depot_id, first_name, last_name, license_no)", d.drivers)
            copy(cur, "stops(id, name, lat, lon)", d.stops)
            copy(cur, "routes(id, type_id, number, name)", d.routes)
            copy(cur, "route_stops(route_id, stop_order, stop_id, km_from_start)", d.route_stops)
            copy(cur, "fare_types(id, name, price)", d.fare_types)
            copy(cur, "cards(id, card_number, fare_type_id, balance)", d.cards)
            copy(cur, "shifts(id, driver_id, vehicle_id, shift_date, start_time, end_time)", d.shifts)
            copy(cur, "trips(id, shift_id, route_id, started_at, finished_at, status)", d.trips)
            copy(cur, "trip_stop_events(trip_id, seq, stop_id, planned_at, arrived_at, departed_at, boarded, alighted)",
                 d.stop_events)
            copy(cur, "trip_telemetry(trip_id, ts, lat, lon, speed, fuel_level, line_voltage, motor_current)", d.telemetry)
            copy(cur, "validations(card_id, trip_id, stop_id, price, created_at)", d.validations)
            copy(cur, "trip_docs(id, doc)", [(doc["_id"], json.dumps(doc, default=str, ensure_ascii=False)) for doc in d.docs])
        c.commit()
    with pg_connect(port, autocommit=True) as c:
        c.execute("vacuum analyze")


def copy(cur, target, rows):
    with cur.copy(f"copy {target} from stdin") as cp:
        for r in rows:
            cp.write_row(r)


def load_mongo(db, d):
    db.drop_collection("trips")
    col = db["trips"]  # для масового завантаження без j=True, як і copy в postgres (одна транзакція)
    for i in range(0, len(d.docs), 500):
        col.insert_many(d.docs[i:i + 500], ordered=False)
    # ті самі індекси, що й у postgres
    col.create_index([("route.id", ASCENDING), ("started_at", ASCENDING)])
    col.create_index("stops.stop_id")
    col.create_index("telemetry.speed")


def pg_size(port):
    with pg_connect(port) as c:
        tables = c.execute("select coalesce(sum(pg_total_relation_size(t)), 0) from unnest(array["
                           "'trips','trip_stop_events','trip_telemetry','validations','shifts','routes',"
                           "'vehicles','drivers','stops']::regclass[]) t").fetchone()[0]
        docs = c.execute("select pg_total_relation_size('trip_docs')").fetchone()[0]
    return int(tables), int(docs)


def mongo_size(db):
    # mongo пише на диск раз на 60 с (checkpoint), без fsync розмір щойно залитих даних буде занижений
    db.client.admin.command("fsync")
    s = db.command("collstats", "trips")
    return int(s["storageSize"] + s["totalIndexSize"])
