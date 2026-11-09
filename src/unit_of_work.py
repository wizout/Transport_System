import os

import psycopg

from repositories import VehicleRepository, DriverRepository, RouteRepository, TripRepository

DSN = "host=localhost port=5432 dbname=transport user=postgres password=postgres"

# setup_db.py записує сюди правильний порт
db_file = os.path.join(os.path.dirname(__file__), "db.txt")
if os.path.exists(db_file):
    with open(db_file, encoding="utf-8") as f:
        DSN = f.read().strip()


class UnitOfWork:
    # одна транзакція на всі репозиторії, без commit() нічого не зберігається

    def __init__(self, user_id, dsn=DSN):
        self.user_id = user_id
        self.dsn = dsn

    def __enter__(self):
        self.conn = psycopg.connect(self.dsn)  # autocommit вимкнений, транзакція стартує сама
        self._set_user()

        self.vehicles = VehicleRepository(self.conn)
        self.drivers = DriverRepository(self.conn)
        self.routes = RouteRepository(self.conn)
        self.trips = TripRepository(self.conn)
        return self

    def _set_user(self):
        # для тригера який ставить updated_by. true - діє тільки до кінця транзакції,
        # тому після commit/rollback ставимо ще раз
        self.conn.execute("select set_config('app.user_id', %s, true)", (str(self.user_id),))

    def commit(self):
        self.conn.commit()
        self._set_user()

    def rollback(self):
        self.conn.rollback()
        self._set_user()

    def __exit__(self, exc_type, exc, tb):
        # все що не закомічено - відкочуємо
        self.conn.rollback()
        self.conn.close()
        return False  # помилку не глушимо
