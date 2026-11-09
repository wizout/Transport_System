from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class Vehicle:
    depot_id: int
    type_id: int
    plate: str
    model: Optional[str] = None
    year_made: Optional[int] = None
    status: str = "active"
    id: Optional[int] = None
    depot: Optional[str] = None
    type: Optional[str] = None


@dataclass
class Driver:
    depot_id: int
    first_name: str
    last_name: str
    license_no: str
    phone: Optional[str] = None
    id: Optional[int] = None
    depot: Optional[str] = None
    can_drive: Optional[str] = None


@dataclass
class Route:
    id: int
    number: str
    name: str
    type: str
    stops_count: int
    length_km: float


@dataclass
class Trip:
    id: int
    status: str
    route_number: str
    driver: str
    plate: str
    started_at: datetime
    finished_at: Optional[datetime]
    passengers: int
    shift_date: Optional[date] = None
