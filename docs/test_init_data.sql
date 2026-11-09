-- тестові дані

select set_config('app.user_id', '1', false);

insert into users(login, full_name, role) values
('admin', 'Котілєвський Григорій', 'admin'),
('disp1', 'Будинський Ігор', 'dispatcher'),
('kasa1', 'Бабенчук Ірена', 'cashier'),
('mech1', 'Гаврищук Тимофій', 'mechanic');

insert into depots(name, address, capacity) values
('Автобусний парк №1', 'вул. Бориспільська, 15', 120),
('Тролейбусне депо №2', 'вул. Деміївська, 37', 80),
('Трамвайне депо ім. Шевченка', 'вул. Кирилівська, 98', 60);

insert into vehicle_types(name, seats, standing) values
('автобус', 30, 70),
('тролейбус', 28, 80),
('трамвай', 40, 150);

insert into vehicles(depot_id, type_id, plate, model, year_made, updated_by) values
(1, 1, 'AA1234KX', 'Богдан А70', 2015, 1),
(1, 1, 'AA5521KX', 'Електрон А185', 2019, 1),
(1, 1, 'AA7710KX', 'MAN Lion''s City', 2012, 1),
(2, 2, 'T-2201', 'Електрон Т19', 2018, 1),
(2, 2, 'T-2202', 'Богдан Т701', 2014, 1),
(3, 3, 'TR-501', 'Електрон Т5L64', 2017, 1),
(3, 3, 'TR-502', 'Tatra T3', 1988, 1);

insert into drivers(depot_id, first_name, last_name, license_no, phone, hired_on, updated_by) values
(1, 'Владлен', 'Дорошенков', 'BXE123456', '0671112233', '2018-03-01', 1),
(1, 'Юліан', 'Сапліков', 'BXE223344', '0502223344', '2020-07-15', 1),
(2, 'Олександр', 'Ласковець', 'BXE334455', '0933334455', '2016-01-10', 1),
(3, 'Ангела', 'Іваницька', 'BXE445566', '0674445566', '2019-09-01', 1),
(1, 'Андріан', 'Цалко', 'BXE556677', '0995556677', '2023-02-20', 1);

insert into driver_licenses(driver_id, type_id, valid_until) values
(1, 1, '2028-01-01'),
(2, 1, '2027-06-01'),
(3, 2, '2027-12-31'),
(3, 1, '2026-01-01'),   -- прострочений
(4, 3, '2029-05-01'),
(5, 1, '2030-01-01');

insert into stops(name, lat, lon, has_shelter, updated_by) values
('Вокзальна', 50.441000, 30.488000, true, 1),
('Площа Перемоги', 50.450400, 30.491600, true, 1),
('Університет', 50.442100, 30.505900, true, 1),
('вул. Кличка Матьє Болл', 50.445200, 30.517400, false, 1),
('Майдан Незалежності', 50.450100, 30.523400, true, 1),
('Європейська площа', 50.454300, 30.529100, true, 1),
('вул. Міндіч Де Кум', 50.444600, 30.545100, false, 1),
('Лівобережна', 50.451900, 30.598700, true, 1),
('Дарниця', 50.455900, 30.612600, true, 1),
('Контрактова площа', 50.465400, 30.515700, true, 1),
('Поштова площа', 50.459200, 30.524700, false, 1),
('Деміївська площа', 50.404800, 30.516300, true, 1),
('вул. Бугров Чо Как', 50.397800, 30.508300, false, 1),
('ВДНГ', 50.382700, 30.477500, true, 1),
('Лук''янівська', 50.462200, 30.482400, true, 1),
('вул. Вирніт Метро', 50.480900, 30.492500, false, 1);

insert into routes(type_id, number, name, updated_by) values
(1, '24', 'Вокзальна - Дарниця', 1),
(1, '62', 'Лук''янівська - Поштова площа', 1),
(2, '11', 'Деміївська площа - ВДНГ', 1),
(3, '14', 'Контрактова площа - вул. Вирніт Метро', 1);

insert into route_stops(route_id, stop_order, stop_id, km_from_start) values
(1, 1, 1, 0), (1, 2, 3, 1.4), (1, 3, 4, 2.3), (1, 4, 5, 3.1), (1, 5, 6, 3.8), (1, 6, 8, 8.2), (1, 7, 9, 9.5),
(2, 1, 15, 0), (2, 2, 2, 1.9), (2, 3, 5, 3.6), (2, 4, 11, 4.4),
(3, 1, 12, 0), (3, 2, 13, 1.1), (3, 3, 14, 3.4),
(4, 1, 10, 0), (4, 2, 16, 2.6);

insert into schedules(route_id, day_type, first_departure, last_departure, interval_min, updated_by) values
(1, 'workday', '05:40', '23:10', 10, 1),
(1, 'weekend', '06:30', '22:30', 15, 1),
(2, 'workday', '06:00', '22:00', 12, 1),
(3, 'workday', '05:30', '23:30', 8, 1),
(3, 'weekend', '06:00', '23:00', 12, 1),
(4, 'workday', '05:50', '22:40', 9, 1);

insert into fare_types(name, price) values
('звичайний', 15.00),
('студентський', 7.50),
('пільговий', 0.00);

insert into passengers(full_name, phone, email) values
('Пухова Соломія', '0631234567', 'solomiia.pukhova@ukr.net'),
('Столярчук Максиміліан', '0679876543', null),
('Мельничук Юліана', null, 'yuliana.melnychuk@gmail.com'),
('Сорокаль Данило', '0501112200', null);

insert into cards(card_number, passenger_id, fare_type_id, balance, updated_by) values
('0001000101', 1, 1, 200, 1),
('0001000102', 2, 2, 50, 1),
('0001000103', 3, 2, 3, 1),
('0001000104', 4, 3, 0, 1),
('0001000105', null, 1, 45, 1);

insert into shifts(driver_id, vehicle_id, shift_date, start_time, end_time) values
(1, 1, current_date - 1, '06:00', '14:00'),
(2, 2, current_date - 1, '14:00', '22:00'),
(3, 4, current_date - 1, '06:00', '14:00'),
(4, 6, current_date - 1, '07:00', '15:00');

insert into trips(shift_id, route_id, started_at, finished_at, status, updated_by) values
(1, 1, current_date - 1 + time '06:10', current_date - 1 + time '06:58', 'finished', 2),
(1, 1, current_date - 1 + time '07:15', current_date - 1 + time '08:09', 'finished', 2),
(2, 2, current_date - 1 + time '14:05', current_date - 1 + time '14:40', 'finished', 2),
(3, 3, current_date - 1 + time '06:20', current_date - 1 + time '06:51', 'finished', 2),
(4, 4, current_date - 1 + time '07:05', current_date - 1 + time '07:22', 'finished', 2);

insert into validations(card_id, trip_id, stop_id, price, created_at) values
(1, 1, 1, 0, current_date - 1 + time '06:12'),
(2, 1, 3, 0, current_date - 1 + time '06:20'),
(5, 2, 1, 0, current_date - 1 + time '07:16'),
(1, 3, 15, 0, current_date - 1 + time '14:06'),
(4, 4, 12, 0, current_date - 1 + time '06:21'),
(2, 5, 10, 0, current_date - 1 + time '07:06');

insert into maintenance(vehicle_id, started_on, finished_on, description, cost, updated_by) values
(3, current_date - 30, current_date - 25, 'заміна гальмівних колодок', 8400, 4),
(7, current_date - 3, null, 'не працює двигун, чекаємо запчастини', null, 4);
