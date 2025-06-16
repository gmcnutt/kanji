from datetime import date
from pony.orm import *


db = Database()


class Kanji(db.Entity):
    id = PrimaryKey(int, auto=True)
    unicode = Required(str, unique=True)
    readings = Set('Reading')
    mnemonic_meaning = Required(str)
    heisig_v1_frame = Optional(int)
    stroke_count = Optional(str)
    meaning_quiz_results = Set('MeaningQuizResult')
    writing_quiz_results = Set('WritingQuizResult')


class Phrase(db.Entity):
    id = PrimaryKey(int, auto=True)
    unicode = Required(str, unique=True)
    meaning = Optional(str)
    hiragana = Optional(str)
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
    student = Required('User')
    streak = Optional(int)
    last_date = Optional(date)
    reading = Required(Reading)


class WritingQuizResult(db.Entity):
    id = PrimaryKey(int, auto=True)
    student = Required('User')
    streak = Optional(int)
    last_date = Optional(date)
    kanji = Required(Kanji)


class MeaningQuizResult(db.Entity):
    id = PrimaryKey(int, auto=True)
    student = Required('User')
    streak = Optional(int)
    last_date = Optional(date)
    kanji = Required(Kanji)


class User(db.Entity):
    id = PrimaryKey(int, auto=True)
    name = Optional(str)
    meaning_quiz_result = Optional(MeaningQuizResult)
    writing_quiz_result = Optional(WritingQuizResult)
    reading_quiz_result = Optional(ReadingQuizResult)
    vocab_quiz_result = Optional('VocabQuizResult')


class VocabQuizResult(db.Entity):
    id = PrimaryKey(int, auto=True)
    student = Required(User)
    streak = Optional(int)
    last_date = Optional(date)
    phrase = Required(Phrase)


def init(filename):
    """Create all the tables as necessary.

    Safe to call more than once on the same database. Returns a handle
    to the database.

    """
    db.bind(provider='sqlite', filename=filename, create_db=True)
    db.generate_mapping(create_tables=True)
    return db
