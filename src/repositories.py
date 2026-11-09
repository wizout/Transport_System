# репозиторії: читання тільки з view, запис тільки через процедури
from psycopg.rows import dict_row

from models import Vehicle, Driver, Route, Trip


class BaseRepository:
    def __init__(self, conn):
        self.conn = conn

    def _all(self, sql, params=()):
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def _one(self, sql, params=()):
        rows = self._all(sql, params)
        return rows[0] if rows else None

    def _call(self, sql, params=()):
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            # якщо в процедури є inout параметр - postgres повертає його рядком
            if cur.description:
                return cur.fetchone()[0]


class VehicleRepository(BaseRepository):
    fields = "id, depot_id, type_id, plate, model, year_made, status, depot, type"

    def get(self, vehicle_id):
        row = self._one(f"select {self.fields} from v_vehicles where id = %s", (vehicle_id,))
        return Vehicle(**row) if row else None

    def get_by_plate(self, plate):
        row = self._one(f"select {self.fields} from v_vehicles where plate = upper(%s)", (plate,))
        return Vehicle(**row) if row else None

    def list(self, depot_id=None):
        if depot_id:
            rows = self._all(f"select {self.fields} from v_vehicles where depot_id = %s order by id", (depot_id,))
        else:
            rows = self._all(f"select {self.fields} from v_vehicles order by id")
        return [Vehicle(**r) for r in rows]

    def add(self, v: Vehicle):
        v.id = self._call("call sp_vehicle_save(null, %s, %s, %s, %s, %s, %s)",
                          (v.depot_id, v.type_id, v.plate, v.model, v.year_made, v.status))
        return v.id

    def update(self, v: Vehicle):
        self._call("call sp_vehicle_save(%s, %s, %s, %s, %s, %s, %s)",
                   (v.id, v.depot_id, v.type_id, v.plate, v.model, v.year_made, v.status))

    def remove(self, vehicle_id):
        self._call("call sp_vehicle_delete(%s)", (vehicle_id,))


class DriverRepository(BaseRepository):
    fields = "id, depot_id, first_name, last_name, license_no, phone, depot, can_drive"

    def get(self, driver_id):
        row = self._one(f"select {self.fields} from v_drivers where id = %s", (driver_id,))
        return Driver(**row) if row else None

    def list(self):
        return [Driver(**r) for r in self._all(f"select {self.fields} from v_drivers order by last_name")]

    def add(self, d: Driver):
        d.id = self._call("call sp_driver_save(null, %s, %s, %s, %s, %s)",
                          (d.depot_id, d.first_name, d.last_name, d.license_no, d.phone))
        return d.id

    def update(self, d: Driver):
        self._call("call sp_driver_save(%s, %s, %s, %s, %s, %s)",
                   (d.id, d.depot_id, d.first_name, d.last_name, d.license_no, d.phone))

    def remove(self, driver_id):
        self._call("call sp_driver_delete(%s)", (driver_id,))

    def grant_license(self, driver_id, type_id, valid_until):
        self._call("call sp_driver_grant_license(%s, %s, %s)", (driver_id, type_id, valid_until))

    def hours(self, driver_id, date_from, date_to):
        return self._one("select fn_driver_hours(%s, %s, %s) as h", (driver_id, date_from, date_to))["h"]


class RouteRepository(BaseRepository):
    def list(self):
        rows = self._all("select id, number, name, type, stops_count, length_km from v_routes order by id")
        return [Route(**r) for r in rows]

    def get_by_number(self, number):
        row = self._one("select id, number, name, type, stops_count, length_km from v_routes where number = %s", (number,))
        return Route(**row) if row else None

    def stops(self, route_id):
        return self._all("select stop_order, stop_id, stop, km_from_start from v_route_stops "
                         "where route_id = %s order by stop_order", (route_id,))


class TripRepository(BaseRepository):
    fields = "id, status, route_number, driver, plate, started_at, finished_at, passengers, shift_date"

    def get(self, trip_id):
        row = self._one(f"select {self.fields} from v_trips where id = %s", (trip_id,))
        return Trip(**row) if row else None

    def list_by_date(self, day):
        rows = self._all(f"select {self.fields} from v_trips where shift_date = %s order by started_at", (day,))
        return [Trip(**r) for r in rows]

    def create_shift(self, driver_id, vehicle_id, day, start, end):
        return self._call("call sp_shift_create(null, %s, %s, %s, %s, %s)",
                          (driver_id, vehicle_id, day, start, end))

    def start(self, shift_id, route_id):
        return self._call("call sp_trip_start(null, %s, %s)", (shift_id, route_id))

    def finish(self, trip_id):
        self._call("call sp_trip_finish(%s)", (trip_id,))

    def validate_card(self, card_number, trip_id, stop_id=None):
        self._call("call sp_validate(%s, %s, %s)", (card_number, trip_id, stop_id))
