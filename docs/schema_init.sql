-- Система управління громадським транспортом (варіант 12)
-- таблиці + ключі

create extension if not exists pg_trgm;

-- користувачі системи (диспетчери, адміни і тд)
-- саме їх id пишеться в updated_by
create table users (
    id serial primary key,
    login varchar(50) not null unique,
    full_name varchar(150) not null,
    role varchar(20) not null default 'dispatcher'
        check (role in ('admin', 'dispatcher', 'cashier', 'mechanic')),
    created_at timestamp not null default now()
);

create table depots (
    id serial primary key,
    name varchar(100) not null unique,
    address varchar(200) not null,
    capacity int not null check (capacity > 0)
);

create table vehicle_types (
    id serial primary key,
    name varchar(50) not null unique,   -- автобус, тролейбус, трамвай
    seats int not null,
    standing int not null
);

create table vehicles (
    id serial primary key,
    depot_id int not null references depots(id),
    type_id int not null references vehicle_types(id),
    plate varchar(15) not null,
    model varchar(80),
    year_made int check (year_made between 1960 and 2100),
    status varchar(20) not null default 'active'
        check (status in ('active', 'repair', 'reserve')),
    updated_at timestamp not null default now(),
    updated_by int references users(id),
    deleted_at timestamp,
    deleted_by int references users(id)
);

create table drivers (
    id serial primary key,
    depot_id int not null references depots(id),
    first_name varchar(60) not null,
    last_name varchar(60) not null,
    license_no varchar(20) not null,
    phone varchar(20),
    hired_on date not null default current_date,
    updated_at timestamp not null default now(),
    updated_by int references users(id),
    deleted_at timestamp,
    deleted_by int references users(id)
);

-- які типи транспорту водій має право водити (m:n)
create table driver_licenses (
    driver_id int not null references drivers(id),
    type_id int not null references vehicle_types(id),
    valid_until date not null,
    primary key (driver_id, type_id)
);

create table routes (
    id serial primary key,
    type_id int not null references vehicle_types(id),
    number varchar(10) not null,
    name varchar(150) not null,
    updated_at timestamp not null default now(),
    updated_by int references users(id),
    deleted_at timestamp,
    deleted_by int references users(id)
);

create table stops (
    id serial primary key,
    name varchar(120) not null,
    lat numeric(9,6) not null,
    lon numeric(9,6) not null,
    has_shelter boolean not null default false,
    updated_at timestamp not null default now(),
    updated_by int references users(id),
    deleted_at timestamp,
    deleted_by int references users(id)
);

-- зупинки маршруту по порядку
create table route_stops (
    route_id int not null references routes(id),
    stop_order int not null check (stop_order > 0),
    stop_id int not null references stops(id),
    km_from_start numeric(6,2) not null default 0,
    primary key (route_id, stop_order)
);

-- розклад: з якого по який час і з яким інтервалом ходить маршрут
create table schedules (
    id serial primary key,
    route_id int not null references routes(id),
    day_type varchar(10) not null check (day_type in ('workday', 'weekend')),
    first_departure time not null,
    last_departure time not null,
    interval_min int not null check (interval_min > 0),
    updated_at timestamp not null default now(),
    updated_by int references users(id),
    check (last_departure > first_departure)
);

-- зміна: водій + машина на день
create table shifts (
    id serial primary key,
    driver_id int not null references drivers(id),
    vehicle_id int not null references vehicles(id),
    shift_date date not null,
    start_time time not null,
    end_time time not null,
    unique (driver_id, shift_date),
    unique (vehicle_id, shift_date)
);

-- рейс (один прохід маршруту)
create table trips (
    id serial primary key,
    shift_id int not null references shifts(id),
    route_id int not null references routes(id),
    started_at timestamp not null default now(),
    finished_at timestamp,
    status varchar(15) not null default 'in_progress'
        check (status in ('in_progress', 'finished', 'cancelled')),
    updated_at timestamp not null default now(),
    updated_by int references users(id)
);

create table fare_types (
    id serial primary key,
    name varchar(50) not null unique,   -- звичайний, студентський, пільговий
    price numeric(8,2) not null check (price >= 0)
);

create table passengers (
    id serial primary key,
    full_name varchar(150) not null,
    phone varchar(20),
    email varchar(100),
    created_at timestamp not null default now()
);

create table cards (
    id serial primary key,
    card_number varchar(20) not null,
    passenger_id int references passengers(id),  -- може бути анонімна
    fare_type_id int not null references fare_types(id),
    balance numeric(10,2) not null default 0 check (balance >= 0),
    issued_at timestamp not null default now(),
    blocked boolean not null default false,
    updated_at timestamp not null default now(),
    updated_by int references users(id),
    deleted_at timestamp,
    deleted_by int references users(id)
);

create table card_topups (
    id serial primary key,
    card_id int not null references cards(id),
    amount numeric(10,2) not null check (amount > 0),
    created_at timestamp not null default now(),
    created_by int references users(id)
);

-- проходи (валідація картки в транспорті)
create table validations (
    id bigserial primary key,
    card_id int not null references cards(id),
    trip_id int not null references trips(id),
    stop_id int references stops(id),
    price numeric(8,2) not null,
    created_at timestamp not null default now()
);

create table maintenance (
    id serial primary key,
    vehicle_id int not null references vehicles(id),
    started_on date not null,
    finished_on date,
    description text not null,
    cost numeric(10,2),
    updated_at timestamp not null default now(),
    updated_by int references users(id),
    check (finished_on is null or finished_on >= started_on)
);
