-- Fixture for tests/test_monthly_revenue.py (loaded after schema.sql).
INSERT INTO fx_rates VALUES ('USD', '2020-01-01', 1.0);
INSERT INTO fx_rates VALUES ('EUR', '2024-01-01', 1.10);
INSERT INTO fx_rates VALUES ('EUR', '2024-02-15', 1.08);
INSERT INTO fx_rates VALUES ('EUR', '2024-04-01', 1.05);
INSERT INTO fx_rates VALUES ('GBP', '2024-01-01', 1.27);

INSERT INTO customers VALUES (1, 'Acme Corp',      'NA',   0);
INSERT INTO customers VALUES (2, 'Brightline GmbH', 'EMEA', 0);
INSERT INTO customers VALUES (3, 'QA Bot',          'NA',   1);
INSERT INTO customers VALUES (4, 'Northwind Ltd',   'EMEA', 0);

-- Acme: January order, two lines, refunded in February.
INSERT INTO orders VALUES (1, 1, '2024-01-10T09:00:00-05:00', 'USD', 'shipped');
INSERT INTO order_lines VALUES (1, 1, 'SKU-100', 2, 1500);
INSERT INTO order_lines VALUES (2, 1, 'SKU-101', 1, 4999);
INSERT INTO refunds VALUES (1, 1, '2024-02-02T12:00:00Z', 1500, 'damaged');

-- Acme: placed on Jan 31 local time, which is already February in UTC.
INSERT INTO orders VALUES (2, 1, '2024-01-31T21:30:00-05:00', 'USD', 'paid');
INSERT INTO order_lines VALUES (3, 2, 'SKU-102', 3, 1000);

-- Brightline: EUR order in January (rate 1.10), refunded in March (still 1.10).
INSERT INTO orders VALUES (3, 2, '2024-01-20T10:00:00+01:00', 'EUR', 'shipped');
INSERT INTO order_lines VALUES (4, 3, 'SKU-200', 1, 10000);
INSERT INTO order_lines VALUES (5, 3, 'SKU-201', 4, 2500);
INSERT INTO refunds VALUES (2, 3, '2024-03-05T08:00:00+01:00', 2000, 'late delivery');

-- Brightline: EUR order in March (rate 1.08), pending.
INSERT INTO orders VALUES (4, 2, '2024-03-02T15:45:00+01:00', 'EUR', 'pending');
INSERT INTO order_lines VALUES (6, 4, 'SKU-202', 1, 3333);

-- Northwind: GBP order in February, cancelled (does not count).
INSERT INTO orders VALUES (5, 4, '2024-02-10T11:00:00Z', 'GBP', 'cancelled');
INSERT INTO order_lines VALUES (7, 5, 'SKU-300', 1, 8000);

-- Northwind: GBP order in February that counts.
INSERT INTO orders VALUES (6, 4, '2024-02-11T11:00:00Z', 'GBP', 'paid');
INSERT INTO order_lines VALUES (8, 6, 'SKU-301', 2, 1999);

-- QA Bot: test account, does not count.
INSERT INTO orders VALUES (7, 3, '2024-02-03T10:00:00-08:00', 'USD', 'paid');
INSERT INTO order_lines VALUES (9, 7, 'SKU-100', 10, 1500);
