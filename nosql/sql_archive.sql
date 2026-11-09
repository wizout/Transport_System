-- SQL-варіант архіву рейсів (те саме, що документ trips в MongoDB)
-- виконується після docs/schema_init.sql
-- документ рейсу в монго = trips + routes + vehicle_types + vehicles + drivers + depots + shifts
--                          + trip_stop_events + stops + trip_telemetry + validations

-- проходження зупинок за рейс (з датчиків дверей)
create table trip_stop_events (
    trip_id int not null references trips(id),
    seq int not null,
    stop_id int not null references stops(id),
    planned_at timestamp not null,
    arrived_at timestamp not null,
    departed_at timestamp not null,
    boarded int not null default 0,
    alighted int not null default 0,
    primary key (trip_id, seq)
);

-- телеметрія з бортового трекера, раз на 30 с
-- в різних типів транспорту різні датчики, тому частина колонок завжди null:
-- автобус - fuel_level, тролейбус - line_voltage, трамвай - motor_current
create table trip_telemetry (
    trip_id int not null references trips(id),
    ts timestamp not null,
    lat numeric(9,6) not null,
    lon numeric(9,6) not null,
    speed numeric(5,1) not null,
    fuel_level numeric(5,1),
    line_voltage numeric(6,1),
    motor_current numeric(6,1),
    primary key (trip_id, ts)
);

-- індекси під ті самі запити, що й у монго
create index ix_tse_stop on trip_stop_events(stop_id);
create index ix_tel_speed on trip_telemetry(speed);
create index ix_val_trip on validations(trip_id);
-- в основній схемі цей індекс створюється разом з процедурами, а сюди процедури не вантажимо
create index ix_trips_route_started on trips(route_id, started_at);

-- додатково: той самий документ, але в postgres jsonb (щоб порівняти не тільки "таблиці vs монго")
create table trip_docs (
    id int primary key,
    doc jsonb not null
);
