
-- DROP TABLE IF EXISTS users;

CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    password TEXT NOT NULL
);
ALTER TABLE users ADD COLUMN last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE users ADD COLUMN username TEXT;

UPDATE users SET username = user_id WHERE username IS NULL;


PRAGMA table_info(users);

ALTER TABLE users ADD COLUMN username TEXT;
ALTER TABLE users ADD COLUMN last_updated TIMESTAMP;

UPDATE users SET last_updated = CURRENT_TIMESTAMP WHERE last_updated IS NULL;


DROP TABLE IF EXISTS youtube_channels;

CREATE TABLE music (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,          -- Name of the uploaded file
    file BLOB NOT NULL,              -- The actual music file in binary format
    user_id TEXT,                    -- Foreign key to reference the uploader
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

ALTER TABLE music ADD COLUMN description TEXT;
ALTER TABLE music ADD COLUMN genre TEXT;
ALTER TABLE music ADD COLUMN image BLOB;


-- DELETE FROM users;


ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0;


UPDATE users SET is_admin = 11 WHERE user_id = '';

CREATE TABLE youtube_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_url TEXT NOT NULL,
    verification_code TEXT NOT NULL,
    verified BOOLEAN DEFAULT 0,
    user_id INTEGER,  -- To store which user submitted the channel
    submission_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);


SELECT *
FROM users


DROP TABLE IF EXISTS music_rpm;

CREATE TABLE music_rpm (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    rpm REAL DEFAULT 0.0,
    revenue REAL DEFAULT 0.0,
    youtube_image BLOB,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

PRAGMA TABLE_info(music_rpm)

SELECT *
from music_rpm

DELETE FROM music_rpm
WHERE rowid NOT IN (
    SELECT MIN(rowid)
    FROM music_rpm
    GROUP BY user_id
);


INSERT INTO music_rpm (user_id)
SELECT user_id FROM users
WHERE user_id NOT IN (SELECT user_id FROM music_rpm);


-- Table to store registration codes (without expiry date)
CREATE TABLE codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE
);

-- Modify the used_codes table to track the expiry date
CREATE TABLE used_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    used_date TIMESTAMP NOT NULL,
    expiry_date TIMESTAMP NOT NULL, -- Add expiry date when the code is used
    FOREIGN KEY (code_id) REFERENCES codes (id),
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);



select *
from used_codes;


SELECT u.user_id, u.username, u.last_updated, m.rpm, m.revenue
FROM users u
LEFT JOIN music_rpm m ON u.user_id = m.user_id
LEFT JOIN used_codes c ON u.user_id = c.user_id;





select *
from users