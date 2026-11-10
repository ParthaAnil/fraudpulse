-- Merchant onboarding database.
-- Columns of `merchants` match ingestion/schemas/merchant.avsc.

CREATE TABLE category_groups (
    group_code  VARCHAR(32)  PRIMARY KEY,
    group_name  VARCHAR(100) NOT NULL
);

CREATE TABLE categories (
    category_code  VARCHAR(32)  PRIMARY KEY,
    category_name  VARCHAR(100) NOT NULL,
    group_code     VARCHAR(32)  NOT NULL,
    CONSTRAINT categories_group_fk
        FOREIGN KEY (group_code) REFERENCES category_groups (group_code)
);

CREATE TABLE merchants (
    merchant_id    CHAR(7)      PRIMARY KEY,
    legal_name     VARCHAR(200) NOT NULL,
    display_name   VARCHAR(100) NOT NULL,
    upi_id         VARCHAR(100) NOT NULL UNIQUE,
    category_code  VARCHAR(32)  NOT NULL,
    city           VARCHAR(64)  NOT NULL,
    status         ENUM('PENDING', 'ACTIVE', 'REJECTED', 'SUSPENDED', 'CLOSED')
                   NOT NULL DEFAULT 'PENDING',
    contact_email  VARCHAR(254) NULL,
    -- Optimistic locking: every update must name the version it read, and adds 1.
    version        INT          NOT NULL DEFAULT 1,
    created_at     TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at     TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
                   ON UPDATE CURRENT_TIMESTAMP(3),
    CONSTRAINT merchants_id_format CHECK (merchant_id REGEXP '^M[0-9]{6}$'),
    CONSTRAINT merchants_category_fk
        FOREIGN KEY (category_code) REFERENCES categories (category_code)
);
