# порівняння швидкодії: MongoDB (документ рейсу) vs PostgreSQL (кілька таблиць) vs PostgreSQL jsonb
#   python bench.py                 - обсяги 1000, 5000, 20000 рейсів
#   python bench.py 1000 50000      - свої обсяги
import csv
import json
import random
import statistics
import sys
import time
from datetime import timedelta
from pathlib import Path

import datagen
import load

RESULTS = Path(__file__).resolve().parent / "results"
MONGO, PG, PGJ = "MongoDB", "PostgreSQL (таблиці)", "PostgreSQL (jsonb)"


def measure(fn, params, warmup=10):
    """повертає список часів у мс. перші warmup запусків не рахуються - прогрів кешу і плану запиту"""
    for p in params[:warmup]:
        fn(p)
    times = []
    for p in params:
        t = time.perf_counter()
        fn(p)
        times.append((time.perf_counter() - t) * 1000)
    return times


# ---------------- сценарії ----------------
# кожен сценарій = однакові параметри для всіх баз + функція для кожної бази

def s_card(pg, col, rnd, d):
    """1. картка рейсу: все про один рейс (диспетчер відкриває рейс, розбір скарги)"""
    ids = [rnd.randint(1, d.n_trips) for _ in range(500)]

    def mongo(i):
        return col.find_one({"_id": i})

    def pg_tables(i):
        # як зробив би звичайний застосунок: шапка + 3 списки
        head = pg.execute("""select t.id, t.status, t.started_at, t.finished_at, r.number, r.name, vt.name,
                                    v.plate, v.model, dr.last_name || ' ' || dr.first_name
                             from trips t join routes r on r.id = t.route_id
                             join vehicle_types vt on vt.id = r.type_id
                             join shifts s on s.id = t.shift_id
                             join vehicles v on v.id = s.vehicle_id
                             join drivers dr on dr.id = s.driver_id
                             where t.id = %s""", (i,)).fetchone()
        stops = pg.execute("""select e.seq, e.stop_id, st.name, e.planned_at, e.arrived_at, e.departed_at, e.boarded, e.alighted
                              from trip_stop_events e join stops st on st.id = e.stop_id
                              where e.trip_id = %s order by e.seq""", (i,)).fetchall()
        tel = pg.execute("select ts, lat, lon, speed, fuel_level, line_voltage, motor_current "
                         "from trip_telemetry where trip_id = %s order by ts", (i,)).fetchall()
        val = pg.execute("select card_id, stop_id, price, created_at from validations where trip_id = %s", (i,)).fetchall()
        return head, stops, tel, val

    def pg_jsonb(i):
        return pg.execute("select doc from trip_docs where id = %s", (i,)).fetchone()

    return ids, {MONGO: mongo, PG: pg_tables, PGJ: pg_jsonb}


def s_route_day(pg, col, rnd, d):
    """2. список рейсів маршруту за день з кількістю пасажирів (екран диспетчера)"""
    params = []
    for _ in range(300):
        tr = d.trips[rnd.randint(0, d.n_trips - 1)]
        day = tr[3].replace(hour=0, minute=0, second=0)
        params.append((tr[2], day, day + timedelta(days=1)))

    def mongo(p):
        return list(col.find({"route.id": p[0], "started_at": {"$gte": p[1], "$lt": p[2]}},
                             {"started_at": 1, "finished_at": 1, "driver.name": 1, "vehicle.plate": 1,
                              "stats.passengers": 1}).sort("started_at", 1))

    def pg_tables(p):
        return pg.execute("""select t.id, t.started_at, t.finished_at, dr.last_name, v.plate,
                                    (select sum(boarded) from trip_stop_events e where e.trip_id = t.id)
                             from trips t join shifts s on s.id = t.shift_id
                             join drivers dr on dr.id = s.driver_id join vehicles v on v.id = s.vehicle_id
                             where t.route_id = %s and t.started_at >= %s and t.started_at < %s
                             order by t.started_at""", p).fetchall()

    return params, {MONGO: mongo, PG: pg_tables}


def s_delays(pg, col, rnd, d):
    """3. середнє запізнення на кожній зупинці маршруту за весь період (аналітика пунктуальності)"""
    params = [rnd.randint(1, 30) for _ in range(30)]

    def mongo(r):
        return list(col.aggregate([
            {"$match": {"route.id": r}},
            {"$unwind": "$stops"},
            {"$group": {"_id": "$stops.stop_id", "avg_delay": {"$avg": "$stops.delay_sec"}, "n": {"$sum": 1}}},
            {"$sort": {"_id": 1}}]))

    def pg_tables(r):
        return pg.execute("""select e.stop_id, avg(extract(epoch from e.arrived_at - e.planned_at)), count(*)
                             from trips t join trip_stop_events e on e.trip_id = t.id
                             where t.route_id = %s group by e.stop_id order by e.stop_id""", (r,)).fetchall()

    return params, {MONGO: mongo, PG: pg_tables}


def s_daily_report(pg, col, rnd, d):
    """4. звіт по всіх маршрутах по днях: пасажири і виручка (важкий запит по всій базі)"""
    params = list(range(10))

    def mongo(_):
        return list(col.aggregate([
            {"$project": {"route": "$route.number", "date": 1,
                          "passengers": {"$sum": "$stops.boarded"}, "revenue": {"$sum": "$validations.price"}}},
            {"$group": {"_id": {"route": "$route", "date": "$date"},
                        "passengers": {"$sum": "$passengers"}, "revenue": {"$sum": "$revenue"}, "trips": {"$sum": 1}}}],
            allowDiskUse=True))

    def pg_tables(_):
        return pg.execute("""select r.number, t.started_at::date, count(*),
                                    sum(p.passengers), sum(coalesce(m.revenue, 0))
                             from trips t join routes r on r.id = t.route_id
                             join (select trip_id, sum(boarded) passengers from trip_stop_events group by trip_id) p
                               on p.trip_id = t.id
                             left join (select trip_id, sum(price) revenue from validations group by trip_id) m
                               on m.trip_id = t.id
                             group by r.number, t.started_at::date""").fetchall()

    return params, {MONGO: mongo, PG: pg_tables}


def s_overspeed(pg, col, rnd, d):
    """5. рейси, де машина їхала швидше N км/год (пошук всередині вкладеного масиву телеметрії)"""
    params = [rnd.choice([70, 75, 80, 85]) for _ in range(30)]

    def mongo(v):
        return [x["_id"] for x in col.find({"telemetry.speed": {"$gt": v}}, {"_id": 1})]

    def pg_tables(v):
        return pg.execute("select distinct trip_id from trip_telemetry where speed > %s", (v,)).fetchall()

    return params, {MONGO: mongo, PG: pg_tables}


def s_stop_history(pg, col, rnd, d):
    """6. всі прибуття на одну зупинку за тиждень (запит "поперек" документів - тут має вигравати sql)"""
    start = datagen.START_DATE
    params = []
    for _ in range(100):
        day = start + timedelta(days=rnd.randint(0, max(0, d.days - 8)))
        params.append((rnd.randint(1, 300), day, day + timedelta(days=7)))

    def mongo(p):
        return list(col.aggregate([
            {"$match": {"stops.stop_id": p[0], "started_at": {"$gte": p[1], "$lt": p[2]}}},
            {"$unwind": "$stops"},
            {"$match": {"stops.stop_id": p[0]}},
            {"$project": {"route": "$route.number", "arrived_at": "$stops.arrived_at", "delay": "$stops.delay_sec"}}]))

    def pg_tables(p):
        return pg.execute("""select r.number, e.arrived_at, extract(epoch from e.arrived_at - e.planned_at)
                             from trip_stop_events e join trips t on t.id = e.trip_id join routes r on r.id = t.route_id
                             where e.stop_id = %s and t.started_at >= %s and t.started_at < %s""", p).fetchall()

    return params, {MONGO: mongo, PG: pg_tables}


def s_insert(pg, col, rnd, d, pg_raw):
    """7. запис завершеного рейсу (одна операція = рейс + зупинки + телеметрія + валідації)"""
    trips = d.extra

    def mongo(x):
        col.insert_one(dict(x["doc"]))

    def pg_tables(x):
        with pg_raw.transaction():
            with pg_raw.cursor() as cur:
                cur.execute("insert into trips(id, shift_id, route_id, started_at, finished_at, status) "
                            "values (%s, %s, %s, %s, %s, %s)", x["trip"])
                cur.executemany("insert into trip_stop_events values (%s, %s, %s, %s, %s, %s, %s, %s)", x["events"])
                cur.executemany("insert into trip_telemetry values (%s, %s, %s, %s, %s, %s, %s, %s)", x["tel"])
                cur.executemany("insert into validations(card_id, trip_id, stop_id, price, created_at) "
                                "values (%s, %s, %s, %s, %s)", x["vals"])

    def pg_jsonb(x):
        with pg_raw.transaction():
            pg_raw.execute("insert into trip_docs(id, doc) values (%s, %s)",
                           (x["doc"]["_id"], json.dumps(x["doc"], default=str, ensure_ascii=False)))

    return trips, {MONGO: mongo, PG: pg_tables, PGJ: pg_jsonb}


def s_update(pg, col, rnd, d, pg_raw):
    """8. дописати в існуючий рейс пізню валідацію (дані з валідатора прийшли із запізненням)"""
    params = [(rnd.randint(1, d.n_trips), rnd.randint(1, 5000)) for _ in range(300)]
    some_time = datagen.START_DATE

    def mongo(p):
        col.update_one({"_id": p[0]}, {"$push": {"validations": {"card_id": p[1], "stop_id": 1, "price": 15.0, "at": some_time}},
                                       "$inc": {"stats.validations": 1, "stats.revenue": 15.0}})

    def pg_tables(p):
        with pg_raw.transaction():
            pg_raw.execute("insert into validations(card_id, trip_id, stop_id, price, created_at) "
                           "values (%s, %s, 1, 15.0, %s)", (p[1], p[0], some_time))

    return params, {MONGO: mongo, PG: pg_tables}


READS = [("1. Картка рейсу (по id)", s_card), ("2. Рейси маршруту за день", s_route_day),
         ("3. Запізнення по зупинках маршруту", s_delays), ("4. Звіт по всіх маршрутах по днях", s_daily_report),
         ("5. Пошук перевищення швидкості", s_overspeed), ("6. Історія однієї зупинки за тиждень", s_stop_history)]
WRITES = [("7. Запис рейсу цілком", s_insert), ("8. Дописати валідацію в рейс", s_update)]


def run_scale(n, port, mdb, rows):
    print(f"\n========== {n} рейсів ==========")
    d = datagen.generate(n)
    print(f"дані: {len(d.trips)} рейсів, {len(d.stop_events)} подій зупинок, {len(d.telemetry)} точок телеметрії, "
          f"{len(d.validations)} валідацій")

    t = time.perf_counter(); load.load_postgres(port, d); t_pg = time.perf_counter() - t
    t = time.perf_counter(); load.load_mongo(mdb, d); t_mg = time.perf_counter() - t
    print(f"завантаження: postgres {t_pg:.1f} c, mongo {t_mg:.1f} c")
    rows.append([n, "0. Масове завантаження (с)", PG, 1, round(t_pg * 1000, 1), round(t_pg * 1000, 1), round(t_pg * 1000, 1)])
    rows.append([n, "0. Масове завантаження (с)", MONGO, 1, round(t_mg * 1000, 1), round(t_mg * 1000, 1), round(t_mg * 1000, 1)])

    pg_tables_size, pg_docs_size = load.pg_size(port)
    mg_size = load.mongo_size(mdb)
    print(f"розмір на диску (з індексами): postgres таблиці {mb(pg_tables_size)}, postgres jsonb {mb(pg_docs_size)}, mongo {mb(mg_size)}")
    for eng, size in [(PG, pg_tables_size), (PGJ, pg_docs_size), (MONGO, mg_size)]:
        rows.append([n, "Розмір на диску (МБ)", eng, 1, round(size / 2**20, 1), "", ""])

    pg = load.pg_connect(port, autocommit=True)
    pg_raw = load.pg_connect(port, autocommit=True)
    col = load.trips_collection(mdb)
    rnd = random.Random(7)

    for name, scen in READS + WRITES:
        if scen in (s_insert, s_update):
            params, fns = scen(pg, col, rnd, d, pg_raw)
        else:
            params, fns = scen(pg, col, rnd, d)
        line = f"{name:<40}"
        for eng, fn in fns.items():
            warm = 0 if scen in (s_insert, s_update) else min(10, len(params) // 3)
            times = measure(fn, params, warmup=warm)
            med = statistics.median(times)
            p95 = sorted(times)[int(len(times) * 0.95) - 1] if len(times) > 1 else times[0]
            rows.append([n, name, eng, len(times), round(med, 3), round(p95, 3), round(statistics.mean(times), 3)])
            line += f" | {short(eng)}: {med:9.2f} мс"
        print(line)
    pg.close(); pg_raw.close()


def short(eng):
    return {MONGO: "mongo", PG: "pg", PGJ: "jsonb"}[eng]


def mb(b):
    return f"{b / 2**20:.0f} МБ"


class Tee:
    """пише вивід і в консоль, і в results/bench_log.txt"""
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)
            st.flush()

    def flush(self):
        pass


def main():
    scales = [int(x) for x in sys.argv[1:]] or [1000, 5000, 20000]
    RESULTS.mkdir(exist_ok=True)
    sys.stdout = Tee(sys.__stdout__, open(RESULTS / "bench_log.txt", "w", encoding="utf-8"))
    port = load.pg_port()
    mdb = load.mongo_db()
    rows = []
    for n in scales:
        run_scale(n, port, mdb, rows)
    with open(RESULTS / "results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["trips", "scenario", "engine", "runs", "median_ms", "p95_ms", "mean_ms"])
        w.writerows(rows)
    try:
        import charts
        charts.build(RESULTS / "results.csv")
    except Exception as e:  # графіки не головне, результати вже в csv
        print("графіки не побудувались:", e, "- можна потім запустити python charts.py")
    print(f"\nрезультати: {RESULTS}")


if __name__ == "__main__":
    main()
