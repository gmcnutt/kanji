from datetime import datetime
from pony.orm import *


db = Database()


class Kanji(db.Entity):
    id = PrimaryKey(int, auto=True)
    unicode = Required(str, unique=True)
    readings = Set('Reading')
    mnemonic_meaning = Required(str, unique=True)
    heisig_v1_frame = Optional(int)
    stroke_count = Optional(str)
    meaning_quiz_results = Set('MeaningQuizResult')
    writing_quiz_results = Set('WritingQuizResult')


class Phrase(db.Entity):
    id = PrimaryKey(int, auto=True)
    unicode = Required(str, unique=True)
    meaning = Required(str)
    hiragana = Required(str)
    readings = Set('Reading')
    vocab_quiz_results = Set('VocabQuizResult')


class Reading(db.Entity):
    id = PrimaryKey(int, auto=True)
    romaji = Optional(str)
    kana = Optional(str)
    kanji = Required(Kanji)
    heisig_v2_frame = Optional(int)
    phrase = Required(Phrase)
    reading_quiz_results = Set('ReadingQuizResult')


class ReadingQuizResult(db.Entity):
    id = PrimaryKey(int, auto=True)
    user = Required('User')
    streak = Optional(int)
    last_date = Optional(datetime)
    reading = Required(Reading)


class WritingQuizResult(db.Entity):
    id = PrimaryKey(int, auto=True)
    user = Required('User')
    streak = Optional(int)
    last_date = Optional(datetime)
    kanji = Required(Kanji)


class MeaningQuizResult(db.Entity):
    id = PrimaryKey(int, auto=True)
    user = Required('User')
    streak = Optional(int)
    last_date = Optional(datetime)
    kanji = Required(Kanji)


class User(db.Entity):
    id = PrimaryKey(int, auto=True)
    name = Optional(str)
    meaning_quiz_result = Set(MeaningQuizResult)
    writing_quiz_result = Set(WritingQuizResult)
    reading_quiz_result = Set(ReadingQuizResult)
    vocab_quiz_result = Set('VocabQuizResult')


class VocabQuizResult(db.Entity):
    id = PrimaryKey(int, auto=True)
    user = Required(User)
    streak = Optional(int)
    last_date = Optional(datetime)
    phrase = Required(Phrase)


def init(filename):
    """Create all the tables as necessary.

    Safe to call more than once on the same database. Returns a handle
    to the database.

    """
    db.bind(provider='sqlite', filename=filename, create_db=True)
    db.generate_mapping(create_tables=True)
    return db
