-- Payments core: users, accounts and balances.
-- Columns of `users` match ingestion/schemas/user.avsc.

CREATE TABLE users (
    user_id     TEXT PRIMARY KEY CHECK (user_id ~ '^U[0-9]{7}$'),
    full_name   TEXT NOT NULL,
    phone       TEXT NOT NULL UNIQUE,
    email       TEXT,
    upi_id      TEXT NOT NULL UNIQUE,
    home_city   TEXT NOT NULL,
    kyc_level   TEXT NOT NULL CHECK (kyc_level IN ('MIN', 'FULL')),
    segment     TEXT NOT NULL CHECK (segment IN ('RETAIL', 'PREMIUM', 'SMALL_BUSINESS')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE accounts (
    account_id     TEXT PRIMARY KEY CHECK (account_id ~ '^A[0-9]{7}$'),
    user_id        TEXT NOT NULL REFERENCES users (user_id),
    -- ADR 0001: money is whole-number paise. A balance can never go below zero.
    balance_paise  BIGINT NOT NULL CHECK (balance_paise >= 0),
    status         TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'FROZEN', 'CLOSED')),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Finding a user's accounts is a common lookup, so index it.
CREATE INDEX accounts_user_id_idx ON accounts (user_id);

-- Keep updated_at correct on every UPDATE, whoever makes the change.
CREATE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_set_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER accounts_set_updated_at
    BEFORE UPDATE ON accounts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
