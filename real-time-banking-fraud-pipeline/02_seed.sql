-- ============================================================
--  SEED DATA  –  realistic banking test data
-- ============================================================

-- ─────────────────────────────────────────────
-- MCC CODES  (subset of common categories)
-- ─────────────────────────────────────────────
INSERT INTO mcc_codes (mcc, description, category, base_risk_score) VALUES
('5411', 'Grocery Stores, Supermarkets',        'Retail',        0.05),
('5812', 'Eating Places, Restaurants',          'Food & Dining', 0.05),
('5541', 'Service Stations',                    'Auto',          0.08),
('6011', 'Financial Institutions - ATM',        'Cash Access',   0.12),
('5912', 'Drug Stores, Pharmacies',             'Healthcare',    0.06),
('4111', 'Transportation – Subways, Buses',     'Travel',        0.10),
('4511', 'Airlines, Air Carriers',              'Travel',        0.15),
('7011', 'Hotels, Motels, Resorts',             'Travel',        0.15),
('5999', 'Miscellaneous Retail',                'Retail',        0.20),
('7995', 'Gambling, Betting',                   'High Risk',     0.75),
('6051', 'Non-Financial Institutions – FX',     'Finance',       0.65),
('5933', 'Pawn Shops',                          'High Risk',     0.70),
('4829', 'Wire Transfers',                      'Finance',       0.60),
('5816', 'Digital Goods – Games',               'Digital',       0.30),
('7372', 'Software / IT Services',              'Technology',    0.15),
('5045', 'Computers, Peripherals',              'Technology',    0.20);

-- ─────────────────────────────────────────────
-- CUSTOMERS
-- ─────────────────────────────────────────────
INSERT INTO customers (customer_id, full_name, email, phone, date_of_birth, country_code, kyc_status, risk_band) VALUES
('a1000000-0000-0000-0000-000000000001', 'Alice Johnson',   'alice@example.com',   '+14155550101', '1985-03-12', 'US', 'VERIFIED', 'LOW'),
('a1000000-0000-0000-0000-000000000002', 'Bob Martinez',    'bob@example.com',     '+14155550102', '1979-07-25', 'US', 'VERIFIED', 'LOW'),
('a1000000-0000-0000-0000-000000000003', 'Carol Chen',      'carol@example.com',   '+14155550103', '1992-11-04', 'US', 'VERIFIED', 'MEDIUM'),
('a1000000-0000-0000-0000-000000000004', 'David Kim',       'david@example.com',   '+14155550104', '1988-05-18', 'US', 'PENDING',  'UNKNOWN'),
('a1000000-0000-0000-0000-000000000005', 'Eve Patel',       'eve@example.com',     '+44207550105', '1995-09-30', 'GB', 'VERIFIED', 'LOW'),
('a1000000-0000-0000-0000-000000000006', 'Frank Osei',      'frank@example.com',   '+49305550106', '1983-01-15', 'DE', 'VERIFIED', 'LOW'),
('a1000000-0000-0000-0000-000000000007', 'Grace Liu',       'grace@example.com',   '+14155550107', '1990-06-22', 'US', 'FLAGGED',  'HIGH'),
('a1000000-0000-0000-0000-000000000008', 'Henry Brown',     'henry@example.com',   '+14155550108', '1975-12-08', 'US', 'VERIFIED', 'MEDIUM');

-- ─────────────────────────────────────────────
-- ACCOUNTS
-- ─────────────────────────────────────────────
INSERT INTO accounts (account_id, customer_id, account_number, account_type, currency, balance, credit_limit, status) VALUES
('b2000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'ACC-10000001', 'CHECKING', 'USD',  12500.00, NULL,     'ACTIVE'),
('b2000000-0000-0000-0000-000000000002', 'a1000000-0000-0000-0000-000000000001', 'ACC-10000002', 'SAVINGS',  'USD',  45000.00, NULL,     'ACTIVE'),
('b2000000-0000-0000-0000-000000000003', 'a1000000-0000-0000-0000-000000000002', 'ACC-10000003', 'CHECKING', 'USD',   3200.00, NULL,     'ACTIVE'),
('b2000000-0000-0000-0000-000000000004', 'a1000000-0000-0000-0000-000000000002', 'ACC-10000004', 'CREDIT',   'USD',      0.00, 5000.00,  'ACTIVE'),
('b2000000-0000-0000-0000-000000000005', 'a1000000-0000-0000-0000-000000000003', 'ACC-10000005', 'CHECKING', 'USD',   8750.50, NULL,     'ACTIVE'),
('b2000000-0000-0000-0000-000000000006', 'a1000000-0000-0000-0000-000000000004', 'ACC-10000006', 'CHECKING', 'USD',    500.00, NULL,     'ACTIVE'),
('b2000000-0000-0000-0000-000000000007', 'a1000000-0000-0000-0000-000000000007', 'ACC-10000007', 'CHECKING', 'USD',    250.00, NULL,     'FROZEN'),
('b2000000-0000-0000-0000-000000000008', 'a1000000-0000-0000-0000-000000000008', 'ACC-10000008', 'CHECKING', 'USD',  22000.00, NULL,     'ACTIVE');

-- ─────────────────────────────────────────────
-- CARDS
-- ─────────────────────────────────────────────
INSERT INTO cards (card_id, account_id, card_type, masked_pan, last_four, expiry_date, network, status) VALUES
('c3000000-0000-0000-0000-000000000001', 'b2000000-0000-0000-0000-000000000001', 'DEBIT',  '4111-****-****-0001', '0001', '2027-12-31', 'VISA',       'ACTIVE'),
('c3000000-0000-0000-0000-000000000002', 'b2000000-0000-0000-0000-000000000004', 'CREDIT', '5200-****-****-0002', '0002', '2026-06-30', 'MASTERCARD', 'ACTIVE'),
('c3000000-0000-0000-0000-000000000003', 'b2000000-0000-0000-0000-000000000003', 'DEBIT',  '4111-****-****-0003', '0003', '2028-03-31', 'VISA',       'ACTIVE'),
('c3000000-0000-0000-0000-000000000004', 'b2000000-0000-0000-0000-000000000005', 'DEBIT',  '4111-****-****-0004', '0004', '2026-09-30', 'VISA',       'ACTIVE'),
('c3000000-0000-0000-0000-000000000005', 'b2000000-0000-0000-0000-000000000007', 'DEBIT',  '4111-****-****-0005', '0005', '2025-12-31', 'VISA',       'BLOCKED'),
('c3000000-0000-0000-0000-000000000006', 'b2000000-0000-0000-0000-000000000008', 'CREDIT', '3700-****-****-0006', '0006', '2027-08-31', 'AMEX',       'ACTIVE');

-- ─────────────────────────────────────────────
-- TRANSACTIONS  (mix of normal + suspicious)
-- ─────────────────────────────────────────────
INSERT INTO transactions (
    txn_id, account_id, card_id, txn_type, amount, currency, direction,
    merchant_name, merchant_mcc, channel, ip_address, device_id,
    country_code, city, status, initiated_at, settled_at
) VALUES
-- Normal grocery purchase
('d4000000-0000-0000-0000-000000000001', 'b2000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000001',
 'PURCHASE', 87.45, 'USD', 'DR', 'Whole Foods Market', '5411', 'POS',
 '192.168.1.10', 'DEV-ALICE-001', 'US', 'San Francisco', 'SETTLED',
 now() - interval '2 days', now() - interval '2 days' + interval '10 minutes'),

-- Restaurant
('d4000000-0000-0000-0000-000000000002', 'b2000000-0000-0000-0000-000000000001', 'c3000000-0000-0000-0000-000000000001',
 'PURCHASE', 42.00, 'USD', 'DR', 'Chipotle Mexican Grill', '5812', 'POS',
 '192.168.1.10', 'DEV-ALICE-001', 'US', 'San Francisco', 'SETTLED',
 now() - interval '1 day', now() - interval '1 day' + interval '5 minutes'),

-- Credit card purchase
('d4000000-0000-0000-0000-000000000003', 'b2000000-0000-0000-0000-000000000004', 'c3000000-0000-0000-0000-000000000002',
 'PURCHASE', 299.99, 'USD', 'DR', 'Amazon.com', '5999', 'ONLINE',
 '10.0.0.55', 'DEV-BOB-001', 'US', 'New York', 'SETTLED',
 now() - interval '3 days', now() - interval '3 days' + interval '1 hour'),

-- ⚠️ SUSPICIOUS: Large gambling txn from flagged customer
('d4000000-0000-0000-0000-000000000004', 'b2000000-0000-0000-0000-000000000007', 'c3000000-0000-0000-0000-000000000005',
 'PURCHASE', 2500.00, 'USD', 'DR', 'BetNow Casino Online', '7995', 'ONLINE',
 '185.23.44.99', 'DEV-UNKNOWN-001', 'CY', 'Nicosia', 'FLAGGED',
 now() - interval '6 hours', NULL),

-- ⚠️ SUSPICIOUS: Wire transfer to overseas
('d4000000-0000-0000-0000-000000000005', 'b2000000-0000-0000-0000-000000000007', NULL,
 'TRANSFER_OUT', 3000.00, 'USD', 'DR', NULL, '4829', 'API',
 '185.23.44.99', NULL, 'NG', 'Lagos', 'FLAGGED',
 now() - interval '5 hours', NULL),

-- Normal ATM withdrawal
('d4000000-0000-0000-0000-000000000006', 'b2000000-0000-0000-0000-000000000003', 'c3000000-0000-0000-0000-000000000003',
 'ATM_WITHDRAWAL', 200.00, 'USD', 'DR', 'Chase ATM', '6011', 'ATM',
 NULL, NULL, 'US', 'Brooklyn', 'SETTLED',
 now() - interval '1 day', now() - interval '1 day' + interval '2 minutes'),

-- Direct deposit (salary)
('d4000000-0000-0000-0000-000000000007', 'b2000000-0000-0000-0000-000000000001', NULL,
 'DIRECT_DEPOSIT', 5500.00, 'USD', 'CR', 'ACME Corp Payroll', NULL, 'API',
 NULL, NULL, 'US', NULL, 'SETTLED',
 now() - interval '7 days', now() - interval '7 days'),

-- ⚠️ SUSPICIOUS: Rapid small transactions (structuring)
('d4000000-0000-0000-0000-000000000008', 'b2000000-0000-0000-0000-000000000006', NULL,
 'TRANSFER_OUT', 9999.00, 'USD', 'DR', NULL, '4829', 'MOBILE',
 '77.12.99.44', 'DEV-DAVID-001', 'US', 'Miami', 'PENDING',
 now() - interval '2 hours', NULL),

-- Airline ticket (normal for Henry)
('d4000000-0000-0000-0000-000000000009', 'b2000000-0000-0000-0000-000000000008', 'c3000000-0000-0000-0000-000000000006',
 'PURCHASE', 1250.00, 'USD', 'DR', 'Delta Air Lines', '4511', 'ONLINE',
 '72.33.101.5', 'DEV-HENRY-001', 'US', 'Atlanta', 'SETTLED',
 now() - interval '4 days', now() - interval '4 days' + interval '30 minutes'),

-- Hotel (normal for Henry)
('d4000000-0000-0000-0000-000000000010', 'b2000000-0000-0000-0000-000000000008', 'c3000000-0000-0000-0000-000000000006',
 'PURCHASE', 890.00, 'USD', 'DR', 'Marriott Hotels', '7011', 'ONLINE',
 '72.33.101.5', 'DEV-HENRY-001', 'US', 'Atlanta', 'SETTLED',
 now() - interval '4 days', now() - interval '3 days');

-- ─────────────────────────────────────────────
-- FRAUD ALERTS  (for the suspicious txns)
-- ─────────────────────────────────────────────
INSERT INTO fraud_alerts (txn_id, alert_type, fraud_score, risk_score, status, notes) VALUES
('d4000000-0000-0000-0000-000000000004', 'HIGH_RISK_MCC',   0.8821, 0.9100, 'CONFIRMED_FRAUD', 'High-risk MCC + foreign IP + blocked card'),
('d4000000-0000-0000-0000-000000000005', 'WIRE_ANOMALY',    0.9102, 0.9500, 'CONFIRMED_FRAUD', 'Large wire to high-risk jurisdiction'),
('d4000000-0000-0000-0000-000000000008', 'STRUCTURING',     0.7650, 0.8200, 'FALSE_POSITIVE',  'Amount just under $10k reporting threshold');
