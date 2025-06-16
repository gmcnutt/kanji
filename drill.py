#!/usr/bin/env python

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pony import orm

import models
from kana import decode, decode_phrase, roma2kata, roma2hira, NotKanaError


AGE_FACTOR = 1.6
TODAY = datetime.today()
FMT = '%Y-%m-%d'
TODAYSTR = TODAY.strftime(FMT)


class UserNotFoundError(Exception):
    pass


def create_or_update(model, obj, **args):
    if obj is None:
        try:
            obj = model(**args)
        except orm.core.CacheIndexError as exc:
            import pdb; pdb.set_trace()
            raise
    else:
        for k, v in args.items():
            setattr(obj, k, v)
    return obj


def dump_unicode_range(title, start, end):
    columns = 8
    index = start
    print(title)
    while index <= end:
        entries = []
        for column in range(columns):
            entries.append(f'{chr(index)} {index:04X}')
            index += 1
            if index > end:
                break
        print(" | ".join(entries))


def run_cmd_dump(args):
    db = models.init(args.database_filename)
    dump_unicode_range("---hiragana---", 0x3041, 0x3096)
    dump_unicode_range("---katakana---", 0x30a1, 0x30fa)
    with orm.db_session:
        print("---kanji---")
        kanjis = models.Kanji.select()
        for kanji in kanjis:
            print(f'{kanji.unicode} {kanji.mnemonic_meaning:16} R1-{kanji.heisig_v1_frame}')
        print("---phrases---")
        phrases = models.Phrase.select()
        for phrase in phrases:
            print(f'{phrase.unicode:6} {phrase.hiragana:16} {phrase.meaning}')
        print("---readings---")
        readings = models.Reading.select()
        for reading in readings:
            print(f'{reading.kanji.unicode} in {reading.phrase.unicode} is {reading.kana} ({reading.romaji})')


def run_cmd_load(args):
    db = models.init(args.database_filename)
    with orm.db_session:
        with open(args.csvfile) as f:
            r = csv.reader(f)
            header = next(r)
            for line in r:
                (pk, rk2, unicode, mnemonic_meaning, stroke_count, on_romaji,
                 heisig_v1_frame, phr,phr_kana,phr_eng) = line
                unicode = decode(unicode)
                on_kata = roma2kata(on_romaji) or None
                phr = decode_phrase(phr) if phr else None
                phr_kana = roma2hira(phr_kana)


                # Create/update the kanji
                kanji = models.Kanji.get(unicode=unicode)
                kanji = create_or_update(
                    models.Kanji,
                    kanji,
                    unicode=unicode,
                    mnemonic_meaning=mnemonic_meaning,
                    heisig_v1_frame=heisig_v1_frame,
                    stroke_count=stroke_count
                )

                # Some kanji have no reading and hence no phrase
                if not phr:
                    continue

                # Create/update the phrase and reading
                phrase = models.Phrase.get(unicode=phr)
                phrase = create_or_update(
                    models.Phrase,
                    phrase,
                    unicode=phr,
                    meaning=phr_eng,
                    hiragana=phr_kana
                )

                #import pdb; pdb.set_trace()
                reading = models.Reading.get(kanji=kanji, phrase=phrase)
                reading = create_or_update(
                    models.Reading,
                    reading,
                    kanji=kanji,
                    phrase=phrase,
                    heisig_v2_frame=rk2,
                    romaji=on_romaji,
                    kana=on_kata
                )


def run_cmd_users(args):
    db = models.init(args.database_filename)
    with orm.db_session:
        users = models.User.select()
        for user in users:
            print(user.name)


def run_cmd_users_add(args):
    db = models.init(args.database_filename)
    with orm.db_session:
        models.User(name=args.username)


def run_cmd_users_import(args):
    # For importing old history file from previous version of the
    # program. Should not need once every thing is setup and working
    # again on this version.
    db = models.init(args.database_filename)
    with open(args.jsonfile) as f:
        history = json.load(f)
    with orm.db_session:
        user = models.User.get(name=args.username)
        if not user:
            raise UserNotFoundError(f"User with name '{args.username}' not found")
        for k, v in history['writing'].items():
            kanji = models.Kanji.get(mnemonic_meaning=k)
            models.WritingQuizResult(
                user=user, streak=v[0], last_date=v[1], kanji=kanji
            )
        for k, v in history['meaning'].items():
            kanji = models.Kanji.get(unicode=k)
            models.MeaningQuizResult(
                user=user, streak=v[0], last_date=v[1], kanji=kanji
            )
        for k, v in history['on'].items():
            kanji = models.Kanji.get(unicode=k)
            for k2, v2 in v.items():
                phrase = models.Phrase.get(unicode=k2)
                reading = models.Reading.get(kanji=kanji, phrase=phrase)
                models.ReadingQuizResult(
                    user=user, streak=v2[0], last_date=v2[1], reading=reading
                )


def get_days_until_due(quiz_result):
    age = TODAY - quiz_result.last_date
    days_to_wait = math.ceil(quiz_result.streak * AGE_FACTOR)
    days_until_due = days_to_wait - age.days
    return max(0, days_until_due)


def run_cmd_stats(args):
    db = models.init(args.database_filename)

    writing_sched = defaultdict(int)
    reading_sched = defaultdict(int)
    meaning_sched = defaultdict(int)

    with orm.db_session:
        user = models.User.get(name=args.username)
        if not user:
            raise UserNotFoundError(f"User with name '{args.username}' not found")
        for result in models.WritingQuizResult.select(user=user):
            writing_sched[get_days_until_due(result)] += 1
        for result in models.ReadingQuizResult.select(user=user):
            reading_sched[get_days_until_due(result)] += 1
        for result in models.MeaningQuizResult.select(user=user):
            meaning_sched[get_days_until_due(result)] += 1

    # Find the maximum day across all schedules
    max_day = max(
        max(writing_sched.keys(), default=-1),
        max(reading_sched.keys(), default=-1),
        max(meaning_sched.keys(), default=-1)
    ) + 1  # Add 1 to include the max day in range

    # Print the schedules
    print('Writing Due: ', end='')
    for x in range(max_day):
        print(f'{writing_sched[x]} ', end='')
    print('')

    print('     On Due: ', end='')
    for x in range(max_day):
        print(f'{reading_sched[x]} ', end='')
    print('')

    print('Meaning Due: ', end='')
    for x in range(max_day):
        print(f'{meaning_sched[x]} ', end='')
    print('')




if __name__ == "__main__":

    pars = argparse.ArgumentParser(description="Kanji Learning Drills")
    pars.add_argument(
        "-db", "--database_filename", help="Database file", default="kanji_db.sql"
    )
    pars.add_argument(
        "-u", "--username", help="User the session is for", default="gmcnutt"
    )


    subp = pars.add_subparsers(help="Commands", required=True)

    dump_parser = subp.add_parser("dump", help="Dump kana and known kanji")
    dump_parser.set_defaults(func=run_cmd_dump)

    load_parser = subp.add_parser(
        'load', help='Load updated kanji and phrase data from CSV'
    )
    load_parser.add_argument(
        '-c', '--csvfile', help="CSV file with kanji data to load",
        default="kanji.csv"
    )
    load_parser.set_defaults(func=run_cmd_load)

    users_parser = subp.add_parser('users', help='Commands to manage users')
    users_parser.set_defaults(func=run_cmd_users)
    users_subp = users_parser.add_subparsers(help="User sub-commands")

    users_add_parser = users_subp.add_parser('add', help='Add a new user')
    users_add_parser.add_argument('username', help='Username to assign user')
    users_add_parser.set_defaults(func=run_cmd_users_add)

    users_import_parser = users_subp.add_parser(
        'import', help="Import a user's quiz history"
    )
    users_import_parser.add_argument('jsonfile', help="JSON file with quiz history")
    users_import_parser.set_defaults(func=run_cmd_users_import)

    stats_parser = subp.add_parser('stats', help="Show drill stats")
    stats_parser.set_defaults(func=run_cmd_stats)

    # review_parser = subp.add_parser('review', help="Review cards that are due")
    # review_parser.add_argument('-d', '--drillname', choices=('write', 'on', 'mean'), default='write')
    # review_parser.add_argument('-l', '--limit', type=int, default=None, help='Limit the number of cards to review')
    # review_parser.set_defaults(func=run_cmd_review)

    # roma_parser = subp.add_parser('roma', help="Convert romaji to hiragana")
    # roma_parser.add_argument('hira')
    # roma_parser.set_defaults(func=run_cmd_roma)

    # uni_parser = subp.add_parser('uni', help="Show the unicode for a character or list of characters")
    # uni_parser.add_argument('kanji')
    # uni_parser.set_defaults(func=run_cmd_uni)

    # convert_parser = subp.add_parser('convert', help="Convert old-style session file to new-style")
    # convert_parser.set_defaults(func=run_cmd_convert)

    args = pars.parse_args()

    try:
        args.func(args)
    except UserNotFoundError as exc:
        print(exc)
