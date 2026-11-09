# генерація тестових даних для архіву рейсів
# одні й ті самі дані потім вантажаться і в postgres (таблиці), і в mongo (документи)
import math
import random
from datetime import datetime, timedelta, time

TYPES = {1: "автобус", 2: "тролейбус", 3: "трамвай"}
FARES = {1: ("звичайний", 15.0), 2: ("студентський", 7.5), 3: ("пільговий", 0.0)}
START_DATE = datetime(2026, 9, 1)
TRIPS_PER_SHIFT = 4

FIRST = ["Андрій", "Олег", "Сергій", "Ігор", "Микола", "Віталій", "Дмитро", "Олена", "Ірина", "Тарас", "Богдан", "Юрій"]
LAST = ["Мельник", "Шевчук", "Коваль", "Бондар", "Ткачук", "Кравець", "Олійник", "Лисенко", "Гончар", "Савчук",
        "Руденко", "Мороз", "Поліщук", "Марченко", "Левченко"]
MODELS = {1: ["Богдан А70", "Електрон А185", "Атаман А092", "MAN Lion's City"],
          2: ["Електрон Т19", "Богдан Т701", "Skoda 24Tr"],
          3: ["Електрон Т5L64", "Tatra T3", "Pesa Twist"]}


class Data:
    """всі таблиці у вигляді списків кортежів + документи для монго"""
    pass


def generate(n_trips, extra_trips=300, seed=42):
    rnd = random.Random(seed)
    d = Data()

    d.depots = [(i, f"Депо №{i}", f"вул. Депівська, {i * 10}", 100) for i in range(1, 6)]
    d.vehicle_types = [(1, "автобус", 30, 70), (2, "тролейбус", 28, 80), (3, "трамвай", 40, 150)]

    # машини: 60% автобуси, 25% тролейбуси, 15% трамваї
    d.vehicles = []
    for i in range(1, 151):
        t = 1 if i <= 90 else (2 if i <= 127 else 3)
        d.vehicles.append((i, rnd.randint(1, 5), t, f"AA{1000 + i}KX", rnd.choice(MODELS[t]), rnd.randint(2005, 2024)))
    d.drivers = []
    d.driver_type = {}
    for i in range(1, 201):
        t = 1 if i <= 120 else (2 if i <= 170 else 3)
        d.drivers.append((i, rnd.randint(1, 5), rnd.choice(FIRST), rnd.choice(LAST), f"BXE{100000 + i}"))
        d.driver_type[i] = t

    # зупинки - точки навколо центру києва
    d.stops = []
    for i in range(1, 301):
        lat = 50.45 + rnd.uniform(-0.08, 0.08)
        lon = 30.52 + rnd.uniform(-0.12, 0.12)
        d.stops.append((i, f"Зупинка {i}", round(lat, 6), round(lon, 6)))
    stop_by_id = {s[0]: s for s in d.stops}

    # маршрути: 30 шт, 10-20 зупинок, впорядковані по довготі щоб маршрут був "лінією"
    d.routes = []
    d.route_stops = []
    route_stops = {}
    for r in range(1, 31):
        t = 1 if r <= 18 else (2 if r <= 25 else 3)
        ids = sorted(rnd.sample(range(1, 301), rnd.randint(10, 20)), key=lambda s: stop_by_id[s][3])
        route_stops[r] = ids
        d.routes.append((r, t, str(r), f"{stop_by_id[ids[0]][1]} - {stop_by_id[ids[-1]][1]}"))
        km = 0.0
        for seq, sid in enumerate(ids, 1):
            if seq > 1:
                km += dist_km(stop_by_id[ids[seq - 2]], stop_by_id[sid])
            d.route_stops.append((r, seq, sid, round(km, 2)))

    d.fare_types = [(k, v[0], v[1]) for k, v in FARES.items()]
    d.cards = []
    card_fare = {}
    for i in range(1, 5001):
        f = rnd.choices([1, 2, 3], [70, 20, 10])[0]
        d.cards.append((i, f"{1000000000 + i}", f, 500.0))
        card_fare[i] = f

    # рейси
    d.shifts, d.trips, d.stop_events, d.telemetry, d.validations = [], [], [], [], []
    d.docs = []
    d.extra = []  # рейси для тесту запису (не вантажаться заздалегідь)

    vehicles_by_type = {t: [v for v in d.vehicles if v[2] == t] for t in TYPES}
    drivers_by_type = {t: [x for x in d.drivers if d.driver_type[x[0]] == t] for t in TYPES}
    routes_by_type = {t: [r for r in d.routes if r[1] == t] for t in TYPES}
    vehicle_by_id = {v[0]: v for v in d.vehicles}
    driver_by_id = {x[0]: x for x in d.drivers}
    route_by_id = {r[0]: r for r in d.routes}

    total = n_trips + extra_trips
    trips_per_day = 400
    trip_id = 0
    shift_id = 0
    day = 0
    while trip_id < total:
        date = START_DATE + timedelta(days=day)
        used_v, used_d = set(), set()
        made_today = 0
        while made_today < trips_per_day and trip_id < total:
            t = rnd.choices([1, 2, 3], [60, 25, 15])[0]
            free_v = [v for v in vehicles_by_type[t] if v[0] not in used_v]
            free_d = [x for x in drivers_by_type[t] if x[0] not in used_d]
            if not free_v or not free_d:
                if all(not [v for v in vehicles_by_type[tt] if v[0] not in used_v] for tt in TYPES):
                    break
                continue
            v = rnd.choice(free_v)
            dr = rnd.choice(free_d)
            used_v.add(v[0]); used_d.add(dr[0])
            shift_id += 1
            start_h = rnd.choice([5, 6, 7, 13, 14])
            d.shifts.append((shift_id, dr[0], v[0], date.date(), time(start_h), time(start_h + 8)))
            route = rnd.choice(routes_by_type[t])
            for j in range(TRIPS_PER_SHIFT):
                if trip_id >= total:
                    break
                trip_id += 1
                made_today += 1
                start = date + timedelta(hours=start_h, minutes=j * 110 + rnd.randint(0, 10))
                is_extra = trip_id > n_trips
                make_trip(rnd, d, trip_id, shift_id, route, vehicle_by_id[v[0]], driver_by_id[dr[0]],
                          route_stops[route[0]], stop_by_id, start, card_fare, is_extra)
        day += 1

    d.n_trips = n_trips
    d.days = day
    return d


def make_trip(rnd, d, trip_id, shift_id, route, vehicle, driver, stops, stop_by_id, start, card_fare, is_extra):
    vtype = vehicle[2]
    trip = (trip_id, shift_id, route[0], start, None, "finished")
    events, tel, vals = [], [], []

    t = start
    delay = 0
    overspeed = rnd.random() < 0.02  # приблизно 2% рейсів з перевищенням
    for seq, sid in enumerate(stops, 1):
        planned = start + timedelta(minutes=(seq - 1) * 3)
        delay = max(-60, delay + rnd.randint(-30, 50))
        arrived = planned + timedelta(seconds=delay)
        departed = arrived + timedelta(seconds=rnd.randint(15, 60))
        boarded = 0 if seq == len(stops) else max(0, int(rnd.gauss(6, 4)))
        alighted = 0 if seq == 1 else max(0, int(rnd.gauss(5, 3)))
        events.append((trip_id, seq, sid, planned, arrived, departed, boarded, alighted))
        for _ in range(boarded):
            if rnd.random() < 0.8:  # не всі валідують :)
                card = rnd.randint(1, 5000)
                vals.append((card, trip_id, sid, FARES[card_fare[card]][1],
                             arrived + timedelta(seconds=rnd.randint(0, 40))))
        t = departed

    finished = events[-1][5]
    trip = trip[:4] + (finished,) + trip[5:]

    # телеметрія раз на 30 секунд, координати - між зупинками
    ts = start
    k = 0
    fuel = rnd.uniform(60, 100)
    while ts <= finished:
        seg = min(int((ts - start).total_seconds() // 180), len(stops) - 2)
        a, b = stop_by_id[stops[seg]], stop_by_id[stops[seg + 1]]
        frac = ((ts - start).total_seconds() % 180) / 180
        lat = a[2] + (b[2] - a[2]) * frac
        lon = a[3] + (b[3] - a[3]) * frac
        speed = max(0.0, rnd.gauss(28, 12))
        if overspeed and rnd.random() < 0.05:
            speed = rnd.uniform(71, 90)
        fuel_level = line_voltage = motor_current = None
        if vtype == 1:
            fuel = max(5, fuel - rnd.uniform(0, 0.3))
            fuel_level = round(fuel, 1)
        elif vtype == 2:
            line_voltage = round(rnd.gauss(600, 15), 1)
        else:
            motor_current = round(abs(rnd.gauss(250, 80)), 1)
        tel.append((trip_id, ts, round(lat, 6), round(lon, 6), round(min(speed, 99.9), 1),
                    fuel_level, line_voltage, motor_current))
        ts += timedelta(seconds=30)
        k += 1

    doc = to_doc(trip, route, vehicle, driver, events, tel, vals, stop_by_id)
    if is_extra:
        d.extra.append({"trip": trip, "events": events, "tel": tel, "vals": vals, "doc": doc})
    else:
        d.trips.append(trip)
        d.stop_events.extend(events)
        d.telemetry.extend(tel)
        d.validations.extend(vals)
        d.docs.append(doc)


def to_doc(trip, route, vehicle, driver, events, tel, vals, stop_by_id):
    """один документ = рейс з усім що до нього відноситься"""
    vtype = vehicle[2]
    sensor = {1: "fuel_level", 2: "line_voltage", 3: "motor_current"}[vtype]
    sensor_i = {1: 5, 2: 6, 3: 7}[vtype]
    passengers = sum(e[6] for e in events)
    return {
        "_id": trip[0],
        "status": trip[5],
        "started_at": trip[3],
        "finished_at": trip[4],
        "date": trip[3].strftime("%Y-%m-%d"),
        "route": {"id": route[0], "number": route[2], "name": route[3], "type": TYPES[route[1]]},
        "vehicle": {"id": vehicle[0], "plate": vehicle[3], "model": vehicle[4], "type": TYPES[vtype], "depot_id": vehicle[1]},
        "driver": {"id": driver[0], "name": f"{driver[3]} {driver[2]}"},
        "stops": [{"seq": e[1], "stop_id": e[2], "name": stop_by_id[e[2]][1],
                   "planned_at": e[3], "arrived_at": e[4], "departed_at": e[5],
                   "delay_sec": int((e[4] - e[3]).total_seconds()),
                   "boarded": e[6], "alighted": e[7]} for e in events],
        # у кожного типу свій датчик - в монго просто інше поле, без null-колонок
        "telemetry": [{"ts": x[1], "lat": float(x[2]), "lon": float(x[3]), "speed": float(x[4]), sensor: float(x[sensor_i])}
                      for x in tel],
        "validations": [{"card_id": v[0], "stop_id": v[2], "price": v[3], "at": v[4]} for v in vals],
        "stats": {"passengers": passengers, "validations": len(vals),
                  "revenue": round(sum(v[3] for v in vals), 2),
                  "max_speed": max(x[4] for x in tel)},
    }


def dist_km(a, b):
    dlat = (b[2] - a[2]) * 111
    dlon = (b[3] - a[3]) * 111 * math.cos(math.radians(a[2]))
    return math.hypot(dlat, dlon)


if __name__ == "__main__":
    import time as _t
    t0 = _t.time()
    data = generate(1000)
    print(f"{len(data.trips)} рейсів, {len(data.stop_events)} подій зупинок, {len(data.telemetry)} телеметрії, "
          f"{len(data.validations)} валідацій, днів {data.days}, {_t.time() - t0:.1f} c")
