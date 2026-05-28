-- =========================================
-- NBP Tracker — initial schema (3NF, simplified)
-- =========================================

-- Wymiar: lista śledzonych walut
CREATE TABLE IF NOT EXISTS currencies (
    code        CHAR(3)      PRIMARY KEY,            -- ISO 4217
    name        TEXT         NOT NULL,
    nbp_table   CHAR(1)      NOT NULL DEFAULT 'A',
    active      BOOLEAN      NOT NULL DEFAULT TRUE,
    added_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Seed wybranych walut (Asia-focused)
INSERT INTO currencies (code, name) VALUES
    ('USD', 'dolar amerykański'),
    ('EUR', 'euro'),
    ('GBP', 'funt szterling'),
    ('JPY', 'jen (Japonia)'),
    ('CNY', 'yuan renminbi (Chiny)'),
    ('HKD', 'dolar Hongkongu'),
    ('SGD', 'dolar singapurski'),
    ('KRW', 'won południowokoreański'),
    ('PHP', 'peso filipińskie'),
    ('MYR', 'ringgit malezyjski')
ON CONFLICT (code) DO NOTHING;

-- Fakt: dzienne kursy (time-series)
CREATE TABLE IF NOT EXISTS exchange_rates_daily (
    currency_code   CHAR(3)        NOT NULL REFERENCES currencies(code),
    effective_date  DATE           NOT NULL,
    rate_pln        NUMERIC(12, 6) NOT NULL,         -- PLN za 1 jednostkę waluty
    table_no        TEXT           NOT NULL,
    fetched_at      TIMESTAMPTZ    NOT NULL DEFAULT now(),
    PRIMARY KEY (currency_code, effective_date)
);

CREATE INDEX IF NOT EXISTS idx_rates_effective_date
    ON exchange_rates_daily (effective_date DESC);

-- Reguły alertów
CREATE TABLE IF NOT EXISTS alert_rules (
    id              SERIAL          PRIMARY KEY,
    currency_code   CHAR(3)         NOT NULL REFERENCES currencies(code),
    threshold_pln   NUMERIC(12, 6)  NOT NULL,
    operator        VARCHAR(2)      NOT NULL CHECK (operator IN ('gt', 'lt', 'ge', 'le')),
    label           TEXT,
    active          BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- Historia wystrzelonych alertów
CREATE TABLE IF NOT EXISTS alerts_sent (
    id              SERIAL          PRIMARY KEY,
    rule_id         INTEGER         NOT NULL REFERENCES alert_rules(id) ON DELETE CASCADE,
    triggered_at    TIMESTAMPTZ     NOT NULL DEFAULT now(),
    rate_at_trigger NUMERIC(12, 6)  NOT NULL,
    effective_date  DATE            NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alerts_rule_id_date
    ON alerts_sent (rule_id, triggered_at DESC);
