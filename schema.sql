PRAGMA foreign_key = ON;

/* A frame from Heisig's Remembering the Kanji Volume 1 (Sixth
   Edition). Each kanji is assigned a canonical meaning for
   memorization purposes. The 'id' is the frame number from that
   book. */

CREATE TABLE kanji (
id INTEGER PRIMARY KEY,
unicode TEXT CHECK(length(unicode) = 1) NOT NULL,
strokes INTEGER,
meaning TEXT
);

/* A meaningful sequence of kanji characters. */
CREATE TABLE phrase (
id INTEGER PRIMARY KEY AUTOINCREMENT,
meaning TEXT NOT NULL,
hiragana TEXT NOT NULL
);

/* An association table between a phrase and it's constituent kanji. */
CREATE TABLE phrase_kanji (
phrase_id INTEGER,
kanji_id INTEGER,
position INTEGER,
PRIMARY KEY (phrase_id, kanji_id),
FOREIGN KEY (phrase_id) REFERENCES phrase(id),
FOREIGN KEY (kanji_id) REFERENCES kanji(id)
);

/* A frame from Heisig's Remembering the Kanji Volume 2 (Fourth
   Edition). Each frame represents a reading of one kanji, illustrated
   by a phrase that employs that reading. The 'id' is the frame number
   from that book. */
CREATE TABLE reading (
id INTEGER PRIMARY key,
kana TEXT NOT NULL,
kanji_id INTEGER,
phrase_id INTEGER,
FOREIGN KEY(kanji_id) REFERENCES kanji(id),
FOREIGN KEY(phrase_id) REFERENCES phrase(id)
);
