-- Activity 4 - normalised relational equivalent of the MongoDB `products` collection.
-- Heterogeneous, category-specific attributes go into an EAV (entity-attribute-value) table;
-- embedded arrays (variants, tags) become child tables with foreign keys.
PRAGMA foreign_keys = ON;

CREATE TABLE products (
    product_id     INTEGER PRIMARY KEY,
    sku            TEXT NOT NULL UNIQUE,
    name           TEXT NOT NULL,
    brand          TEXT NOT NULL,
    department     TEXT,
    category       TEXT NOT NULL,
    price          REAL NOT NULL CHECK (price >= 0),
    mrp            REAL NOT NULL CHECK (mrp >= price),
    currency       TEXT NOT NULL CHECK (currency = 'INR'),
    rating_avg     REAL CHECK (rating_avg BETWEEN 0 AND 5),
    rating_count   INTEGER CHECK (rating_count >= 0),
    stock          INTEGER NOT NULL CHECK (stock >= 0),
    warehouse      TEXT NOT NULL,
    reorder_level  INTEGER,
    status         TEXT NOT NULL CHECK (status IN ('active', 'discontinued')),
    created_at     TEXT NOT NULL,
    updated_at     TEXT
);

CREATE TABLE product_specs (          -- EAV: one row per attribute, values stored as TEXT
    product_id  INTEGER NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    spec_key    TEXT NOT NULL,
    spec_value  TEXT,
    PRIMARY KEY (product_id, spec_key)
);

CREATE TABLE product_variants (
    product_id  INTEGER NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    size        TEXT NOT NULL,
    color       TEXT NOT NULL,
    stock       INTEGER NOT NULL CHECK (stock >= 0),
    PRIMARY KEY (product_id, size, color)
);

CREATE TABLE product_tags (
    product_id  INTEGER NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    tag         TEXT NOT NULL,
    PRIMARY KEY (product_id, tag)
);

CREATE INDEX idx_products_category_price ON products(category, price);
CREATE INDEX idx_products_brand          ON products(brand);
CREATE INDEX idx_specs_key               ON product_specs(spec_key, spec_value);
CREATE INDEX idx_variants_size_color     ON product_variants(size, color);
