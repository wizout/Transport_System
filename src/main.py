import random
from datetime import date, time, timedelta

import psycopg

from models import Vehicle, Driver
from unit_of_work import UnitOfWork

DISPATCHER = 2  # disp1 з таблиці users


def print_vehicles(uow):
    for v in uow.vehicles.list():
        print(f"  {v.id:>3}  {v.plate:<10} {v.model or '':<18} {v.type:<10} {v.status:<8} {v.depot}")


def main():
    n = random.randint(1000, 9999)  # щоб можна було запускати кілька разів

    print("=== машини на початку ===")
    with UnitOfWork(DISPATCHER) as uow:
        print_vehicles(uow)

    # 1. новий водій + нова машина + зміна + рейс - все однією транзакцією
    print("\n=== новий водій, машина і рейс по маршруту 24 ===")
    with UnitOfWork(DISPATCHER) as uow:
        route = uow.routes.get_by_number("24")

        bus = Vehicle(depot_id=1, type_id=1, plate=f"aa{n}te", model="Атаман А092", year_made=2021)
        uow.vehicles.add(bus)

        driver = Driver(depot_id=1, first_name="Ілько", last_name="Москаленко",
                        license_no=f"BXE{n}00", phone="0661234567")
        uow.drivers.add(driver)
        uow.drivers.grant_license(driver.id, 1, date.today() + timedelta(days=365))

        shift_id = uow.trips.create_shift(driver.id, bus.id, date.today(), time(8, 0), time(16, 0))
        trip_id = uow.trips.start(shift_id, route.id)

        stops = uow.routes.stops(route.id)
        uow.trips.validate_card("0001000101", trip_id, stops[0]["stop_id"])
        uow.trips.validate_card("0001000102", trip_id, stops[1]["stop_id"])
        uow.trips.finish(trip_id)

        uow.commit()

        t = uow.trips.get(trip_id)
        print(f"  рейс #{t.id}: маршрут {t.route_number}, {t.driver}, {t.plate}, пасажирів {t.passengers}, {t.status}")

    # 2. помилка посеред транзакції -> нічого не зберігається
    print("\n=== спроба з помилкою (водій без допуску на тролейбус) ===")
    with UnitOfWork(DISPATCHER) as uow:
        count_before = len(uow.vehicles.list())
    try:
        with UnitOfWork(DISPATCHER) as uow:
            trolley = Vehicle(depot_id=2, type_id=2, plate=f"t-{n}", model="Електрон Т19", year_made=2022)
            uow.vehicles.add(trolley)
            print(f"  додали тролейбус {trolley.plate}, id={trolley.id} (ще не закомічено)")

            # Дорошенков (id=1) має права тільки на автобус
            shift_id = uow.trips.create_shift(1, trolley.id, date.today(), time(9, 0), time(17, 0))
            uow.trips.start(shift_id, uow.routes.get_by_number("11").id)
            uow.commit()
    except psycopg.Error as e:
        print("  помилка з бази:", e.diag.message_primary)
    with UnitOfWork(DISPATCHER) as uow:
        print(f"  машин було {count_before}, стало {len(uow.vehicles.list())} - транзакцію відкотило")

    # 3. зміна і soft delete (на машині з кроку 1)
    print("\n=== оновлення і soft delete ===")
    with UnitOfWork(DISPATCHER) as uow:
        v = uow.vehicles.get(bus.id)
        v.status = "reserve"
        uow.vehicles.update(v)
        uow.vehicles.remove(v.id)
        uow.commit()
        print(f"  {v.plate} видалено, в v_vehicles є: {uow.vehicles.get(v.id) is not None}")

    print("\n=== машини в кінці ===")
    with UnitOfWork(DISPATCHER) as uow:
        print_vehicles(uow)
        print("\nводії:")
        for d in uow.drivers.list():
            name = f"{d.last_name} {d.first_name}"
            print(f"  {name:<20} {d.license_no:<10} може: {d.can_drive}")


if __name__ == "__main__":
    main()
