#!/usr/bin/env python

import argparse
import csv
import json
import math
import random
from collections import defaultdict
from datetime import datetime, timedelta
from pony import orm
import sys, tty, termios
from termcolor import colored, cprint

import models
from kana import decode, decode_phrase, roma2kata, roma2hira, NotKanaError


AGE_FACTOR = 1.6
TODAY = datetime.today()
FMT = '%Y-%m-%d'
TODAYSTR = TODAY.strftime(FMT)


class UserNotFoundError(Exception):
    pass


class DuplicateError(Exception):
    pass


def getch():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch


def prompt(str):
    print(str, end='', flush=True)
    return getch()


def backspace(str):
    x = '\b' * len(str)
    sys.stdout.write(x)
    y = ' ' * len(str)
    sys.stdout.write(y)
    sys.stdout.write(x)


def create_or_update(model, obj, **args):
    if obj is None:
        obj = model(**args)
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


def get_days_until_due(quiz_result):
    age = TODAY - quiz_result.last_date
    days_to_wait = math.ceil(quiz_result.streak * AGE_FACTOR)
    days_until_due = days_to_wait - age.days
    return max(0, days_until_due)


def add_missing_quiz_results(user):
    for kanji in models.Kanji.select():
        qr = models.WritingQuizResult.get(kanji=kanji, user=user)
        if not qr:
            models.WritingQuizResult(user=user, kanji=kanji, last_date=TODAY)
        qr = models.MeaningQuizResult.get(kanji=kanji, user=user)
        if not qr:
            models.MeaningQuizResult(user=user, kanji=kanji, last_date=TODAY)
    for reading in models.Reading.select():
        qr = models.ReadingQuizResult.get(user=user, reading=reading)
        if not qr:
            models.ReadingQuizResult(user=user, reading=reading)


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
        for user in models.User.select():
            add_missing_quiz_results(user)


def run_cmd_users(args):
    db = models.init(args.database_filename)
    with orm.db_session:
        users = models.User.select()
        for user in users:
            print(user.name)


def run_cmd_users_add(args):
    db = models.init(args.database_filename)
    with orm.db_session:
        user = models.User.get(name=args.username)
        if user:
            raise DuplicateError(f"User '{user.name}' already exists")
        user = models.User(name=args.username)
        add_missing_quiz_results(user)


def run_cmd_users_del(args):
    db = models.init(args.database_filename)
    with orm.db_session:
        user = models.User.get(name=args.username)
        if user:
            user.delete()
        else:
            raise UserNotFoundError(f"User with name '{args.username}' not found")


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
            qr = models.WritingQuizResult.get(user=user, kanji=kanji)
            create_or_update(
                models.WritingQuizResult, qr,
                user=user, streak=v[0], last_date=v[1], kanji=kanji
            )
        for k, v in history['meaning'].items():
            kanji = models.Kanji.get(unicode=k)
            qr = models.MeaningQuizResult.get(user=user, kanji=kanji)
            create_or_update(
                models.MeaningQuizResult, qr,
                user=user, streak=v[0], last_date=v[1], kanji=kanji
            )
        for k, v in history['on'].items():
            kanji = models.Kanji.get(unicode=k)
            for k2, v2 in v.items():
                phrase = models.Phrase.get(unicode=k2)
                reading = models.Reading.get(kanji=kanji, phrase=phrase)
                qr = models.ReadingQuizResult.get(user=user, reading=reading)
                create_or_update(
                    models.ReadingQuizResult, qr,
                    user=user, streak=v2[0], last_date=v2[1], reading=reading
                )


def run_cmd_stats(args):
    db = models.init(args.database_filename)

    writing_sched = defaultdict(int)
    reading_sched = defaultdict(int)
    meaning_sched = defaultdict(int)

    with orm.db_session:
        user = models.User.get(name=args.username)
        if not user:
            raise UserNotFoundError(f"User with name '{args.username}' not found")
        add_missing_quiz_results(user)
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

    print('Reading Due: ', end='')
    for x in range(max_day):
        print(f'{reading_sched[x]} ', end='')
    print('')

    print('Meaning Due: ', end='')
    for x in range(max_day):
        print(f'{meaning_sched[x]} ', end='')
    print('')


def run_cmd_roma2hira(args):
    kana, codes = roma2hira(args.roma, return_codes=True)
    print(f'{kana} {",".join(codes)}')


def run_cmd_uni(args):
    for k in args.kanji:
        print(f'{k} {hex(ord(k))}')


def run_review_loop(user, model, limit, test_user, instructions):

    # Get due questions
    due = []
    results = model.select(user=user)
    due = [r for r in results if (0 == get_days_until_due(r))]
    if not due:
        cprint(f'{colored("Nothing due", "green")}')
        return 0

    # Randomize and limit the list of questions
    random.shuffle(due)
    available = len(due)
    if limit:
        due = due[:limit]
    total = len(due)
    cprint(f'Reviewing ({total}/{available} cards)', "yellow")
    cprint(instructions, "yellow")
    fails = []

    # Ask the questions and track failures. Update the quiz results.
    for i, qr in enumerate(due):
        if test_user(qr, i, total):
            qr.streak += 1
            cprint(f"ok {qr.streak}", "green", attrs=["bold"])
        else:
            qr.streak = 0
            fails.append(qr)
        qr.last_date = TODAYSTR

    num_correct = total - len(fails)
    percent = round(num_correct * 100 / total)
    cprint(f'You passed {num_correct}/{total} cards ({percent}%)', "green")

    # Review failures.
    while fails:
        failed = len(fails)
        cprint(f"Reviewing failures ({failed} cards)", "yellow")
        refails = []
        for i, qr in enumerate(fails):
            if not test_user(qr, i, failed):
                refails.append(qr)
            print()
        fails = refails
    return total


def test_user_writing(qr, i, total):
    """Run on each kanji due for writing."""
    instr1 = '<Press any key to check>'
    instr2 = 'correct? <y/n>'
    kanji = qr.kanji
    question = kanji.mnemonic_meaning
    answer = kanji.unicode

    # Show the mnemonic meaning and prompt the user to write the answer.
    prompt(
        f'({i+1}/{total}) {colored(question, attrs=["bold"]):16} {colored(instr1, "yellow")}'
    )

    # Ask the user if he wrote it correctly.
    backspace(instr1)
    ok = prompt(
        f' {colored(answer,"cyan", attrs=["bold"])} ({kanji.stroke_count}) {colored(instr2, "yellow")}'
    )
    backspace(instr2)
    passed = ok == 'y'

    # If not, show the frame number in the Heisig Volume 1 book
    if not passed:
        cprint(f"fail (R1-{kanji.heisig_v1_frame})", "red", attrs=["bold"])

    return passed


def test_user_meaning(qr, i, total):
    kanji = qr.kanji
    promptstr = f'({i+1}/{total}) {colored(kanji.unicode, "cyan", attrs=["bold"])}? '
    r = input(promptstr)

    backup = f'\033[1A'
    sys.stdout.write(backup)
    print(f'{promptstr}{r} ', end='')

    ok = r == kanji.mnemonic_meaning
    if not ok:
        cprint(f"should be ", 'red', end='')
        cprint(f"{kanji.mnemonic_meaning}", 'red', attrs=['underline'], end='')
        cprint(f" fail (R1-{kanji.heisig_v1_frame})", "red", attrs=["bold"])
    return ok


def test_user_reading(qr, i, total):
    reading = qr.reading
    kanji = reading.kanji
    phrase = reading.phrase
    promptstr = f'({i+1}/{total}) {colored(kanji.unicode, "cyan", attrs=["bold"])} in {colored(phrase.unicode, "cyan")}? '
    r = input(promptstr)
    backup = f'\033[1A'
    sys.stdout.write(backup)
    print(f'{promptstr}\b\b ', end='')
    if r:
        try:
            on = roma2kata(r)
        except (KeyError, NotKanaError):
            on = '<invalid>'
    else:
        on = '?'
    ok = on == reading.kana
    if ok:
        cprint(f'{on} ', "green", end='')
        cprint(f'in {colored(phrase.hiragana, "light_grey")} ({phrase.meaning}) ', end='')
    else:
        cprint(f'{colored(on, "red")} should be {colored(reading.kana, "magenta")} (', end='')
        cprint(f'{reading.romaji}', attrs=["underline"], end='')
        cprint(f') in {colored(phrase.hiragana, "cyan")} ({phrase.meaning}) ', end='')
        cprint(f"fail (R2-{reading.heisig_v2_frame})", "red", attrs=["bold"])
    return ok


def run_cmd_review(args):
    db = models.init(args.database_filename)
    with orm.db_session:
        user = models.User.get(name=args.username)
        if not user:
            raise UserNotFoundError(f"User with name '{args.username}' not found")

        if args.drillname == 'write':
            run_review_loop(
                user, models.WritingQuizResult, args.limit, test_user_writing,
                'Given the meaning, write the kanji'
            )
        elif args.drillname == 'mean':
            run_review_loop(
                user, models.MeaningQuizResult, args.limit, test_user_meaning,
                'Given the kanji, type the meaning'
            )
        elif args.drillname == 'read':
            run_review_loop(
                user, models.ReadingQuizResult, args.limit, test_user_reading,
                'Given the kanji and the phrase, type the "on" in romaji'
            )

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

    users_del_parser = users_subp.add_parser('del', help='Delete an existing user')
    users_del_parser.add_argument('username', help='Username to delete')
    users_del_parser.set_defaults(func=run_cmd_users_del)

    users_import_parser = users_subp.add_parser(
        'import', help="Import a user's quiz history"
    )
    users_import_parser.add_argument('jsonfile', help="JSON file with quiz history")
    users_import_parser.set_defaults(func=run_cmd_users_import)

    stats_parser = subp.add_parser('stats', help="Show drill stats")
    stats_parser.set_defaults(func=run_cmd_stats)

    roma_parser = subp.add_parser('roma2hira', help="Convert romaji to hiragana")
    roma_parser.add_argument('roma')
    roma_parser.set_defaults(func=run_cmd_roma2hira)

    uni_parser = subp.add_parser(
        'unicode',
        help="Show the unicode for a character or list of characters"
    )
    uni_parser.add_argument('kanji')
    uni_parser.set_defaults(func=run_cmd_uni)

    review_parser = subp.add_parser('review', help="Review cards that are due")
    review_parser.add_argument(
        '-d', '--drillname', choices=('write', 'read', 'mean'), default='write'
    )
    review_parser.add_argument(
        '-l', '--limit', type=int, default=None,
        help='Limit the number of cards to review'
    )
    review_parser.set_defaults(func=run_cmd_review)


    args = pars.parse_args()

    try:
        args.func(args)
    except (UserNotFoundError, DuplicateError) as exc:
        print(exc)
