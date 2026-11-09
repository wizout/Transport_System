-- індекси, функції, тригери, процедури, view

-- ---------- індекси ----------

-- btree на зовнішні ключі які часто джойняться
create index ix_vehicles_depot on vehicles(depot_id);
create index ix_drivers_depot on drivers(depot_id);
create index ix_trips_shift on trips(shift_id);
create index ix_trips_route_started on trips(route_id, started_at);  -- складений
create index ix_validations_card on validations(card_id);

-- унікальні часткові: номер машини / посвідчення / картки має бути унікальним
-- тільки серед не видалених записів (бо soft delete)
create unique index ux_vehicles_plate on vehicles(plate) where deleted_at is null;
create unique index ux_drivers_license on drivers(license_no) where deleted_at is null;
create unique index ux_routes_number on routes(type_id, number) where deleted_at is null;

-- hash - пошук картки тільки по точному номеру
create index ix_cards_number_hash on cards using hash (card_number);

-- gin з триграмами - пошук зупинки по частині назви (like '%майдан%')
create index ix_stops_name_trgm on stops using gin (name gin_trgm_ops);


-- ---------- функції ----------

-- id юзера який зараз працює (з коду ставиться через set_config)
create or replace function current_app_user() returns int
language sql stable as $$
    select nullif(current_setting('app.user_id', true), '')::int
$$;

-- довжина маршруту в км (по останній зупинці)
create or replace function fn_route_length(p_route_id int) returns numeric
language sql stable as $$
    select coalesce(max(km_from_start), 0) from route_stops where route_id = p_route_id
$$;

-- скільки годин водій відпрацював за період (по рейсах)
create or replace function fn_driver_hours(p_driver_id int, p_from date, p_to date) returns numeric
language sql stable as $$
    select coalesce(round(sum(extract(epoch from (t.finished_at - t.started_at))) / 3600, 2), 0)
    from trips t
    join shifts s on s.id = t.shift_id
    where s.driver_id = p_driver_id
      and t.status = 'finished'
      and s.shift_date between p_from and p_to
$$;

-- кількість пасажирів за рейс
create or replace function fn_trip_passengers(p_trip_id int) returns int
language sql stable as $$
    select count(*)::int from validations where trip_id = p_trip_id
$$;


-- ---------- тригери ----------

-- оновлює updated_at і updated_by при будь-якій зміні
create or replace function trg_touch() returns trigger
language plpgsql as $$
begin
    new.updated_at := now();
    new.updated_by := coalesce(current_app_user(), new.updated_by);
    return new;
end $$;

create trigger touch_vehicles before update on vehicles for each row execute function trg_touch();
create trigger touch_drivers before update on drivers for each row execute function trg_touch();
create trigger touch_routes before update on routes for each row execute function trg_touch();
create trigger touch_stops before update on stops for each row execute function trg_touch();
create trigger touch_schedules before update on schedules for each row execute function trg_touch();
create trigger touch_trips before update on trips for each row execute function trg_touch();
create trigger touch_cards before update on cards for each row execute function trg_touch();
create trigger touch_maintenance before update on maintenance for each row execute function trg_touch();


-- забороняє фізичне видалення там де є soft delete
create or replace function trg_no_hard_delete() returns trigger
language plpgsql as $$
begin
    raise exception 'з таблиці % не можна видаляти, треба через soft delete (deleted_at)', tg_table_name;
end $$;

create trigger nodel_vehicles before delete on vehicles for each row execute function trg_no_hard_delete();
create trigger nodel_drivers before delete on drivers for each row execute function trg_no_hard_delete();
create trigger nodel_routes before delete on routes for each row execute function trg_no_hard_delete();
create trigger nodel_stops before delete on stops for each row execute function trg_no_hard_delete();
create trigger nodel_cards before delete on cards for each row execute function trg_no_hard_delete();


-- перед стартом рейсу: машина не в ремонті, водій має права на цей тип транспорту
create or replace function trg_trip_check() returns trigger
language plpgsql as $$
declare
    v_vehicle vehicles%rowtype;
    v_driver int;
    v_route_type int;
begin
    select v.* into v_vehicle
    from shifts s join vehicles v on v.id = s.vehicle_id
    where s.id = new.shift_id;

    select driver_id into v_driver from shifts where id = new.shift_id;
    select type_id into v_route_type from routes where id = new.route_id and deleted_at is null;

    if v_route_type is null then
        raise exception 'маршрут % не знайдено', new.route_id;
    end if;
    if v_vehicle.deleted_at is not null or v_vehicle.status <> 'active' then
        raise exception 'машина % зараз не може виїхати (статус %)', v_vehicle.plate, v_vehicle.status;
    end if;
    if v_vehicle.type_id <> v_route_type then
        raise exception 'тип машини не підходить для маршруту';
    end if;
    if not exists (select 1 from driver_licenses
                   where driver_id = v_driver and type_id = v_route_type
                     and valid_until >= current_date) then
        raise exception 'у водія % немає дійсного допуску на цей тип транспорту', v_driver;
    end if;
    return new;
end $$;

create trigger check_trip before insert on trips for each row execute function trg_trip_check();


-- при валідації картки знімаємо гроші по тарифу
create or replace function trg_validation_pay() returns trigger
language plpgsql as $$
declare
    v_card cards%rowtype;
    v_price numeric;
begin
    select * into v_card from cards where id = new.card_id for update;

    if v_card.id is null or v_card.deleted_at is not null then
        raise exception 'картка не знайдена';
    end if;
    if v_card.blocked then
        raise exception 'картка % заблокована', v_card.card_number;
    end if;

    select price into v_price from fare_types where id = v_card.fare_type_id;

    if v_card.balance < v_price then
        raise exception 'недостатньо коштів на картці % (баланс %, треба %)', v_card.card_number, v_card.balance, v_price;
    end if;

    update cards set balance = balance - v_price where id = v_card.id;
    new.price := v_price;
    return new;
end $$;

create trigger pay_validation before insert on validations for each row execute function trg_validation_pay();


-- ремонт: коли додали запис - машина в repair, коли закрили - назад active
create or replace function trg_maintenance_status() returns trigger
language plpgsql as $$
begin
    if new.finished_on is null then
        update vehicles set status = 'repair' where id = new.vehicle_id;
    elsif tg_op = 'UPDATE' and old.finished_on is null then
        update vehicles set status = 'active' where id = new.vehicle_id;
    end if;
    return new;
end $$;

create trigger maintenance_status after insert or update on maintenance for each row execute function trg_maintenance_status();


-- ---------- процедури ----------
-- якщо p_id = null то insert, інакше update. id повертається назад через inout

create or replace procedure sp_vehicle_save(
    inout p_id int,
    p_depot_id int, p_type_id int, p_plate varchar, p_model varchar, p_year int,
    p_status varchar default 'active')
language plpgsql as $$
begin
    if p_id is null then
        insert into vehicles(depot_id, type_id, plate, model, year_made, status, updated_by)
        values (p_depot_id, p_type_id, upper(p_plate), p_model, p_year, p_status, current_app_user())
        returning id into p_id;
    else
        update vehicles
        set depot_id = p_depot_id, type_id = p_type_id, plate = upper(p_plate),
            model = p_model, year_made = p_year, status = p_status
        where id = p_id and deleted_at is null;
        if not found then
            raise exception 'машина % не знайдена', p_id;
        end if;
    end if;
end $$;

create or replace procedure sp_vehicle_delete(p_id int)
language plpgsql as $$
begin
    if exists (select 1 from trips t join shifts s on s.id = t.shift_id
               where s.vehicle_id = p_id and t.status = 'in_progress') then
        raise exception 'машина зараз на рейсі, видалити не можна';
    end if;
    update vehicles set deleted_at = now(), deleted_by = current_app_user()
    where id = p_id and deleted_at is null;
end $$;

create or replace procedure sp_driver_save(
    inout p_id int,
    p_depot_id int, p_first_name varchar, p_last_name varchar, p_license_no varchar, p_phone varchar)
language plpgsql as $$
begin
    if p_id is null then
        insert into drivers(depot_id, first_name, last_name, license_no, phone, updated_by)
        values (p_depot_id, p_first_name, p_last_name, p_license_no, p_phone, current_app_user())
        returning id into p_id;
    else
        update drivers
        set depot_id = p_depot_id, first_name = p_first_name, last_name = p_last_name,
            license_no = p_license_no, phone = p_phone
        where id = p_id and deleted_at is null;
        if not found then
            raise exception 'водій % не знайдений', p_id;
        end if;
    end if;
end $$;

create or replace procedure sp_driver_delete(p_id int)
language sql as $$
    update drivers set deleted_at = now(), deleted_by = current_app_user()
    where id = p_id and deleted_at is null;
$$;

create or replace procedure sp_driver_grant_license(p_driver_id int, p_type_id int, p_valid_until date)
language sql as $$
    insert into driver_licenses(driver_id, type_id, valid_until)
    values (p_driver_id, p_type_id, p_valid_until)
    on conflict (driver_id, type_id) do update set valid_until = excluded.valid_until;
$$;

create or replace procedure sp_route_save(inout p_id int, p_type_id int, p_number varchar, p_name varchar)
language plpgsql as $$
begin
    if p_id is null then
        insert into routes(type_id, number, name, updated_by)
        values (p_type_id, p_number, p_name, current_app_user())
        returning id into p_id;
    else
        update routes set type_id = p_type_id, number = p_number, name = p_name
        where id = p_id and deleted_at is null;
    end if;
end $$;

create or replace procedure sp_route_delete(p_id int)
language sql as $$
    update routes set deleted_at = now(), deleted_by = current_app_user()
    where id = p_id and deleted_at is null;
$$;

-- додати зупинку в кінець маршруту
create or replace procedure sp_route_add_stop(p_route_id int, p_stop_id int, p_km numeric)
language plpgsql as $$
declare
    v_next int;
begin
    select coalesce(max(stop_order), 0) + 1 into v_next from route_stops where route_id = p_route_id;
    insert into route_stops(route_id, stop_order, stop_id, km_from_start)
    values (p_route_id, v_next, p_stop_id, p_km);
    update routes set updated_at = now() where id = p_route_id;  -- щоб видно було що маршрут мінявся
end $$;

create or replace procedure sp_shift_create(
    inout p_id int, p_driver_id int, p_vehicle_id int, p_date date, p_start time, p_end time)
language plpgsql as $$
begin
    insert into shifts(driver_id, vehicle_id, shift_date, start_time, end_time)
    values (p_driver_id, p_vehicle_id, p_date, p_start, p_end)
    returning id into p_id;
end $$;

create or replace procedure sp_trip_start(inout p_id int, p_shift_id int, p_route_id int)
language plpgsql as $$
begin
    if exists (select 1 from trips where shift_id = p_shift_id and status = 'in_progress') then
        raise exception 'у цій зміні вже є незакінчений рейс';
    end if;
    insert into trips(shift_id, route_id, updated_by)
    values (p_shift_id, p_route_id, current_app_user())
    returning id into p_id;
end $$;

create or replace procedure sp_trip_finish(p_id int)
language plpgsql as $$
begin
    update trips set finished_at = now(), status = 'finished'
    where id = p_id and status = 'in_progress';
    if not found then
        raise exception 'рейс % не в процесі', p_id;
    end if;
end $$;

create or replace procedure sp_card_topup(p_card_id int, p_amount numeric)
language plpgsql as $$
begin
    update cards set balance = balance + p_amount
    where id = p_card_id and deleted_at is null and not blocked;
    if not found then
        raise exception 'картку % не можна поповнити', p_card_id;
    end if;
    insert into card_topups(card_id, amount, created_by) values (p_card_id, p_amount, current_app_user());
end $$;

create or replace procedure sp_validate(p_card_number varchar, p_trip_id int, p_stop_id int)
language plpgsql as $$
declare
    v_card int;
begin
    select id into v_card from cards where card_number = p_card_number and deleted_at is null;
    if v_card is null then
        raise exception 'картка % не знайдена', p_card_number;
    end if;
    if not exists (select 1 from trips where id = p_trip_id and status = 'in_progress') then
        raise exception 'рейс % не активний', p_trip_id;
    end if;
    -- ціну і списання рахує тригер pay_validation
    insert into validations(card_id, trip_id, stop_id, price) values (v_card, p_trip_id, p_stop_id, 0);
end $$;


-- ---------- view ----------

create or replace view v_vehicles as
select v.id, v.plate, v.model, v.year_made, v.status,
       v.depot_id, d.name as depot, v.type_id, vt.name as type,
       v.updated_at, u.login as updated_by
from vehicles v
join depots d on d.id = v.depot_id
join vehicle_types vt on vt.id = v.type_id
left join users u on u.id = v.updated_by
where v.deleted_at is null;

create or replace view v_drivers as
select dr.id, dr.first_name, dr.last_name, dr.license_no, dr.phone, dr.hired_on,
       dr.depot_id, d.name as depot,
       (select string_agg(vt.name, ', ' order by vt.name)
        from driver_licenses dl join vehicle_types vt on vt.id = dl.type_id
        where dl.driver_id = dr.id and dl.valid_until >= current_date) as can_drive,
       dr.updated_at, u.login as updated_by
from drivers dr
join depots d on d.id = dr.depot_id
left join users u on u.id = dr.updated_by
where dr.deleted_at is null;

create or replace view v_routes as
select r.id, r.number, r.name, r.type_id, vt.name as type,
       (select count(*) from route_stops rs where rs.route_id = r.id) as stops_count,
       fn_route_length(r.id) as length_km,
       r.updated_at
from routes r
join vehicle_types vt on vt.id = r.type_id
where r.deleted_at is null;

create or replace view v_route_stops as
select rs.route_id, r.number as route_number, rs.stop_order, s.id as stop_id, s.name as stop, rs.km_from_start
from route_stops rs
join routes r on r.id = rs.route_id and r.deleted_at is null
join stops s on s.id = rs.stop_id and s.deleted_at is null;

create or replace view v_trips as
select t.id, t.status, t.started_at, t.finished_at,
       t.route_id, r.number as route_number,
       t.shift_id, s.shift_date,
       s.driver_id, dr.last_name || ' ' || dr.first_name as driver,
       s.vehicle_id, v.plate,
       fn_trip_passengers(t.id) as passengers
from trips t
join routes r on r.id = t.route_id
join shifts s on s.id = t.shift_id
join drivers dr on dr.id = s.driver_id
join vehicles v on v.id = s.vehicle_id;

create or replace view v_cards as
select c.id, c.card_number, c.balance, c.blocked, ft.name as fare, ft.price,
       p.full_name as owner, c.issued_at
from cards c
join fare_types ft on ft.id = c.fare_type_id
left join passengers p on p.id = c.passenger_id
where c.deleted_at is null;

-- пасажиропотік по маршрутах по днях
create or replace view v_route_daily_stats as
select r.number as route_number, t.started_at::date as day,
       count(distinct t.id) as trips,
       count(val.id) as passengers,
       coalesce(sum(val.price), 0) as revenue
from trips t
join routes r on r.id = t.route_id
left join validations val on val.trip_id = t.id
group by r.number, t.started_at::date;

-- машини що зараз у ремонті
create or replace view v_vehicles_in_repair as
select v.plate, v.model, m.started_on, m.description, current_date - m.started_on as days
from maintenance m
join vehicles v on v.id = m.vehicle_id
where m.finished_on is null and v.deleted_at is null;
