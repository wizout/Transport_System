# Redis (key-value) - "живий" шар системи: де зараз машини, хто на якому маршруті, кеш, лічильники
# дані тут живуть секунди/хвилини, тому їм не місце ні в postgres, ні в архіві mongo
import json
import os
import time

import redis

r = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=int(os.getenv("REDIS_PORT", 6379)), decode_responses=True)
r.ping()

# зупинки з основної бази (lon, lat)
STOPS = {
    "Вокзальна": (30.488000, 50.441000),
    "Університет": (30.505900, 50.442100),
    "вул. Кличка Матьє Болл": (30.517400, 50.445200),
    "Майдан Незалежності": (30.523400, 50.450100),
    "Європейська площа": (30.529100, 50.454300),
    "Лівобережна": (30.598700, 50.451900),
}
VEHICLES = [  # номер, маршрут, lon, lat, швидкість
    ("AA1234KX", "24", 30.4950, 50.4415, 31),
    ("AA5521KX", "24", 30.5600, 50.4520, 44),
    ("AA7710KX", "62", 30.5220, 50.4490, 12),
    ("T-2201", "11", 30.5160, 50.4060, 27),
    ("TR-501", "14", 30.5150, 50.4660, 0),
]


def show(cmd, res):
    print(f"> {cmd}\n  {res}")


def section(t):
    print(f"\n===== {t} =====")


r.flushdb()

section("1. STRING + TTL: кеш інформації про маршрут")
route = {"number": "24", "name": "Вокзальна - Дарниця", "type": "автобус", "stops": 7, "length_km": 9.5}
r.set("route:24", json.dumps(route, ensure_ascii=False), ex=300)  # кеш на 5 хв, потім знову з postgres
show("SET route:24 '{...}' EX 300", "OK")
show("GET route:24", r.get("route:24"))
show("TTL route:24", r.ttl("route:24"))

section("2. HASH: поточний стан машини")
for plate, rt, lon, lat, speed in VEHICLES:
    r.hset(f"vehicle:{plate}", mapping={"route": rt, "speed": speed, "passengers": 0, "updated": int(time.time())})
    r.expire(f"vehicle:{plate}", 120)  # трекер мовчить 2 хв - машина зникає з "онлайну"
show("HSET vehicle:AA1234KX route 24 speed 31 passengers 0 ...", "5 машин записано")
r.hincrby("vehicle:AA1234KX", "passengers", 7)
r.hincrby("vehicle:AA1234KX", "passengers", -2)
show("HINCRBY vehicle:AA1234KX passengers 7 / -2", r.hget("vehicle:AA1234KX", "passengers"))
show("HGETALL vehicle:AA1234KX", r.hgetall("vehicle:AA1234KX"))

section("3. GEO: координати машин і пошук найближчих")
for plate, rt, lon, lat, speed in VEHICLES:
    r.geoadd("vehicles:pos", (lon, lat, plate))
for name, (lon, lat) in STOPS.items():
    r.geoadd("stops:pos", (lon, lat, name))
lon, lat = STOPS["Майдан Незалежності"]
near = r.geosearch("vehicles:pos", longitude=lon, latitude=lat, radius=2, unit="km", withdist=True, sort="ASC")
show("GEOSEARCH vehicles:pos FROMLONLAT <Майдан> BYRADIUS 2 km ASC WITHDIST", near)
show("GEODIST stops:pos Вокзальна Лівобережна km", r.geodist("stops:pos", "Вокзальна", "Лівобережна", unit="km"))
near_stop = r.geosearch("stops:pos", member="Університет", radius=1.5, unit="km", withdist=True, sort="ASC")
show("GEOSEARCH stops:pos FROMMEMBER Університет BYRADIUS 1.5 km", near_stop)

section("4. SET: які машини зараз на маршруті")
for plate, rt, *_ in VEHICLES:
    r.sadd(f"route:{rt}:vehicles", plate)
show("SMEMBERS route:24:vehicles", r.smembers("route:24:vehicles"))
show("SISMEMBER route:24:vehicles T-2201", r.sismember("route:24:vehicles", "T-2201"))
show("SCARD route:24:vehicles", r.scard("route:24:vehicles"))

section("5. SORTED SET: найзавантаженіші зупинки за сьогодні")
for stop, n in [("Вокзальна", 120), ("Майдан Незалежності", 340), ("Університет", 95), ("Лівобережна", 210)]:
    r.zincrby("stops:boarded:2026-11-09", n, stop)
r.zincrby("stops:boarded:2026-11-09", 15, "Університет")
show("ZINCRBY stops:boarded:2026-11-09 15 Університет", r.zscore("stops:boarded:2026-11-09", "Університет"))
show("ZREVRANGE stops:boarded:2026-11-09 0 2 WITHSCORES", r.zrevrange("stops:boarded:2026-11-09", 0, 2, withscores=True))

section("6. SET NX EX: захист від повторної оплати (картку прикладають двічі за хвилину)")
card = "1000000101"
first = r.set(f"card:{card}:lock", "AA1234KX", nx=True, ex=60)
second = r.set(f"card:{card}:lock", "AA1234KX", nx=True, ex=60)
show(f"SET card:{card}:lock AA1234KX NX EX 60   (перший прохід)", f"{first} -> списуємо гроші")
show(f"SET card:{card}:lock AA1234KX NX EX 60   (через 2 секунди)", f"{second} -> вже оплачено, не списуємо")

section("7. LIST: останні валідації (стрічка для диспетчера)")
for i, c in enumerate(["1000000101", "1000000102", "1000000105", "1000000103"]):
    r.lpush("validations:recent", f"{c}|AA1234KX|{i}")
r.ltrim("validations:recent", 0, 99)  # тримаємо тільки 100 останніх
show("LPUSH validations:recent ... ; LTRIM validations:recent 0 99", "ok")
show("LRANGE validations:recent 0 2", r.lrange("validations:recent", 0, 2))

section("8. STREAM: потік телеметрії (потім пачками йде в mongo)")
for plate, rt, lon, lat, speed in VEHICLES[:3]:
    r.xadd("telemetry", {"plate": plate, "lat": lat, "lon": lon, "speed": speed})
show("XADD telemetry * plate AA1234KX lat ... speed 31", "3 записи")
show("XLEN telemetry", r.xlen("telemetry"))
show("XRANGE telemetry - + COUNT 2", r.xrange("telemetry", count=2))

section("9. INCR: лічильник проходів за день")
for _ in range(3):
    r.incr("stats:validations:2026-11-09")
show("INCR stats:validations:2026-11-09 (x3)", r.get("stats:validations:2026-11-09"))

section("10. Ключі та видалення")
show("KEYS vehicle:*", sorted(r.keys("vehicle:*")))
show("DEL vehicle:TR-501", r.delete("vehicle:TR-501"))
show("EXISTS vehicle:TR-501", r.exists("vehicle:TR-501"))
