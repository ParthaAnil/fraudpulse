-- Reference data. The codes match CATEGORIES in the generator's population.py.

INSERT INTO category_groups (group_code, group_name) VALUES
    ('DAILY_NEEDS', 'Daily Needs'),
    ('FOOD',        'Food and Dining'),
    ('TRANSPORT',   'Transport'),
    ('SHOPPING',    'Shopping'),
    ('TRAVEL',      'Travel'),
    ('BILLS',       'Bills and Utilities');

INSERT INTO categories (category_code, category_name, group_code) VALUES
    ('GROCERY',       'Grocery and Supermarkets', 'DAILY_NEEDS'),
    ('PHARMACY',      'Pharmacy',                 'DAILY_NEEDS'),
    ('RESTAURANT',    'Restaurants',              'FOOD'),
    ('FOOD_DELIVERY', 'Food Delivery',            'FOOD'),
    ('FUEL',          'Fuel Stations',            'TRANSPORT'),
    ('TAXI',          'Taxi and Ride Hailing',    'TRANSPORT'),
    ('ELECTRONICS',   'Electronics',              'SHOPPING'),
    ('CLOTHING',      'Clothing and Fashion',     'SHOPPING'),
    ('TRAVEL',        'Travel and Hotels',        'TRAVEL'),
    ('UTILITIES',     'Utility Bills',            'BILLS');
