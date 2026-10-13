"""Fake customers for local demos: `flask seed-demo`.

Demo rows are identified by phone numbers in the fictional 555-01xx range, so re-running
replaces them without touching real customers. No emails are sent.
"""
import random
from datetime import datetime, timedelta

from .extensions import db
from .models import Area, Customer, area_for_zip

DEMO_PHONE_MARK = '555-01'  # 555-0100..0199 are reserved fictional numbers
AREA_CODES = ['831', '209', '559', '661', '805', '760', '951', '909', '619']

# Central CA down to San Diego. Longer prefixes override shorter ones.
DEMO_AREAS = [
    ('950', 'Hollister / Gilroy'),
    ('939', 'Monterey / Salinas'),
    ('953', 'Modesto / Merced'),
    ('936', 'Fresno'),
    ('937', 'Fresno'),
    ('932', 'Visalia / Hanford'),
    ('933', 'Bakersfield'),
    ('934', 'SLO / Santa Barbara'),
    ('930', 'Ventura County'),
    ('935', 'High Desert'),
    ('913', 'Santa Clarita / Agua Dulce'),
    ('923', 'San Bernardino'),
    ('92307', 'Victor Valley'),
    ('92345', 'Victor Valley'),
    ('92371', 'Victor Valley'),
    ('928', 'Norco / Corona'),
    ('925', 'Riverside / Temecula'),
    ('926', 'Orange County'),
    ('922', 'Coachella Valley'),
    ('920', 'North San Diego County'),
    ('919', 'East San Diego County'),
]

# (zip, town) — real zips so the area grouping looks right
TOWNS = [
    ('95023', 'Hollister'), ('93907', 'Prunedale'), ('95358', 'Modesto'), ('95361', 'Oakdale'),
    ('95340', 'Merced'), ('93635', 'Los Banos'), ('93611', 'Clovis'), ('93706', 'Fresno'),
    ('93277', 'Visalia'), ('93230', 'Hanford'), ('93308', 'Bakersfield'), ('93561', 'Tehachapi'),
    ('93446', 'Paso Robles'), ('93422', 'Atascadero'), ('93460', 'Santa Ynez'), ('93023', 'Ojai'),
    ('93021', 'Moorpark'), ('93536', 'Lancaster'), ('93510', 'Acton'), ('91390', 'Agua Dulce'),
    ('92399', 'Yucaipa'), ('92307', 'Apple Valley'), ('92345', 'Hesperia'), ('92371', 'Phelan'),
    ('92860', 'Norco'), ('92592', 'Temecula'), ('92562', 'Murrieta'), ('92595', 'Wildomar'),
    ('92584', 'Menifee'), ('92544', 'Hemet'), ('92539', 'Anza'), ('92536', 'Aguanga'),
    ('92570', 'Perris'), ('92676', 'Silverado'), ('92675', 'San Juan Capistrano'), ('92201', 'Indio'),
    ('92065', 'Ramona'), ('92082', 'Valley Center'), ('92028', 'Fallbrook'), ('91901', 'Alpine'),
    ('91935', 'Jamul'),
]

FIRST = ['Maria', 'Jake', 'Linda', 'Carlos', 'Becky', 'Tom', 'Sarah', 'Luis', 'Kim', 'Dave',
         'Jenna', 'Ray', 'Amy', 'Hector', 'Megan', 'Bill', 'Rosa', 'Kyle', 'Tina', 'Frank',
         'Holly', 'Marco', 'Debbie', 'Shane', 'Erin', 'Pete', 'Gina', 'Dustin', 'Carol', 'Jose']
LAST = ['Alvarez', 'Bennett', 'Carter', 'Dominguez', 'Ellis', 'Foster', 'Garcia', 'Hughes',
        'Ibarra', 'Jensen', 'Keller', 'Lopez', 'Miller', 'Nguyen', 'Ortiz', 'Parker', 'Ramirez',
        'Silva', 'Turner', 'Vasquez', 'Walker', 'Young', 'Zamora', 'Brooks', 'Cruz']

HERDS = ['Alpaca', 'Alpaca', 'Alpaca, Llama', 'Llama', 'Sheep', 'Sheep, Goat', 'Goat', 'Pig',
         'Pig, Goat', 'Alpaca, Sheep']

NOTES = ['', '', '', 'Gate code 4471', 'Call when 30 min out', '2 are skittish, need halters',
         'Dogs on property', 'Long gravel driveway, ok for truck', 'Prefers mornings',
         'Referred by neighbor', 'Had them sheared last year by someone else', 'Weekends only']


def seed_demo(count=50, rng_seed=7):
    rng = random.Random(rng_seed)

    for prefix, name in DEMO_AREAS:
        area = Area.query.filter_by(zip_prefix=prefix).first()
        if area:
            area.name = name
        else:
            db.session.add(Area(zip_prefix=prefix, name=name))
    db.session.flush()

    old = Customer.query.filter(Customer.phone.contains(DEMO_PHONE_MARK)).all()
    for c in old:
        db.session.delete(c)  # cascades to their trip stops
    db.session.flush()

    for i in range(count):
        zip_code, town = TOWNS[i % len(TOWNS)]
        first, last = rng.choice(FIRST), rng.choice(LAST)
        animals = rng.choice(HERDS)
        herd = f'{rng.randint(2, 14)} {animals.split(",")[0].lower()}s'
        db.session.add(Customer(
            name=f'{first} {last}',
            email=None if i % 17 == 5 else f'{first}.{last}{i}@example.com'.lower(),
            phone=f'({rng.choice(AREA_CODES)}) {DEMO_PHONE_MARK}{i % 100:02d}',
            zip_code=zip_code,
            area=area_for_zip(zip_code),
            animals=animals,
            created_at=datetime.now() - timedelta(days=rng.randint(1, 300)),
            notes='. '.join(n for n in [f'{town} — {herd}', rng.choice(NOTES)] if n),
        ))

    db.session.commit()
    return count, len(old)
