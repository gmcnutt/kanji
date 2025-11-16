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
from kana import (decode, decode_phrase, roma2kata, roma2hira, kata2hira,
                  NotKanaError,
                  is_hiragana, is_kanji, is_katakana)


AGE_FACTOR = 1.7  # 1.6 too low
TODAY = datetime.today()
FMT = '%Y-%m-%d %H:%M:%S'


class UserNotFoundError(Exception):
    pass


class DuplicateError(Exception):
    pass


class NotKanjiError(Exception):
    pass


class BadEntryError(Exception):
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


def is_knowable_phrase(phrase):
    # Try to build the phrase's hiragana from the consituent kanji
    # characters using known readings. Iff we can, the phrase is
    # knowable.
    target = phrase.hiragana  # phrase to build
    reading_hira = ''         # last match, if any

    # For each kanji or kana in the phrase, match it to the target
    # prefix then chop it off the front to advance the target for the
    # next match.
    for c in phrase.unicode:

        # For the odd case where the phrase includes katakana, convert
        # to hiragana and fall through to the next check (note that
        # the target is always hiragana).
        if is_katakana(c):
            c = kata2hira(c)
            import pdb; pdb.set_trace()

        # If it's hiragana it should match the target.
        if is_hiragana(c):
            if c != target[0]:
                raise BadEntryError(f'Expected {c} as next letter in {target} for {phrase.unicode} ({phrase.hiragana})')
            target = target[1:]
            continue

        # Check for the special iteration character which has no fixed
        # reading. It's a shorthand for "repeat the last kanji". Retry
        # the last match.
        if c == '々':
            if not target.startswith(reading_hira):
                raise BadEntryError(
                    f'Found 々 but {target} does not start with "{reading_hira}" '\
                    'for {phrase.unicode} ({phrase.hiragana})'
                )
            else:
                target = target[len(reading_hira):]
                continue

        # It must be kanji at this point, or bad data. Note that rare
        # kanji might not pass this test (the test can be modified to
        # check other unicode ranges if necessary).
        if not is_kanji(c):
            raise NotKanjiError(f'{c} does not appear to be kanji but appears in {phrase.unicode} ({phrase.hiragana})')

        # If the kanji is not in our database then the phrase is not
        # knowable.
        kanji = models.Kanji.get(unicode=c)
        if kanji is None:
            return False

        # Find all the known readings for the kanji. Find the first
        # one that matches the prefix of our target and advance the
        # target. If we can't find one, the phrase is not knowable.
        reading_hira = ''
        found = False
        for reading in models.Reading.select(kanji=kanji):
            reading_hira = roma2hira(reading.romaji)
            if target.startswith(reading_hira):
                target = target[len(reading_hira):]
                found = True
                break


        if not found:
            return False

    return True


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
    for phrase in models.Phrase.select():
        if is_knowable_phrase(phrase):
            qr = models.VocabQuizResult.get(user=user, phrase=phrase)
            if not qr:
                models.VocabQuizResult(user=user, phrase=phrase)
            qr = models.PhraseQuizResult.get(user=user, hiragana=phrase.hiragana)
            if not qr:
                qr = models.PhraseQuizResult(user=user, hiragana=phrase.hiragana)
            qr.phrases.add(phrase)
            

def run_cmd_dump(args):
    if args.specific=='kana':
        dump_unicode_range("---hiragana---", 0x3041, 0x3096)
        dump_unicode_range("---katakana---", 0x30a1, 0x30fa)
    else:
        db = models.init(args.database_filename)
        with orm.db_session:
            if args.specific=='kanji':
                print("---kanji---")
                kanjis = models.Kanji.select()
                for kanji in kanjis:
                    print(f'{colored(kanji.unicode, "cyan", attrs=["bold"])} {kanji.mnemonic_meaning:16} R1-{kanji.heisig_v1_frame} {colored(kanji.stroke_count, "yellow")}')
            elif args.specific=='phrases':
                print("---phrases---")
                phrases = models.Phrase.select()
                for phrase in phrases:
                    print(f'{phrase.unicode:6} {phrase.hiragana:16} {phrase.meaning}')
            elif args.specific=='readings':
                print("---readings---")
                readings = models.Reading.select()
                for reading in readings:
                    try:
                        print(f'{reading.kanji.unicode} in {reading.phrase.unicode} is {reading.kana} ({reading.romaji})')
                    except Exception as e:
                        cprint(f"Error in reading {reading}", "red")
                        print(e)


def run_cmd_load(args):
    db = models.init(args.database_filename)
    with orm.db_session:
        with open(args.csvfile) as f:
            r = csv.reader(f)
            header = next(r)
            for line in r:
                (rk2, unicode, mnemonic_meaning, stroke_count, on_romaji,
                 heisig_v1_frame, phr,phr_kana,phr_eng) = line
                unicode = decode(unicode)
                on_kata = roma2kata(on_romaji) or None
                phr = decode_phrase(phr, unicode) if phr else None
                phr_kana = roma2hira(phr_kana)
                heisig_v1_frame = heisig_v1_frame or None  # empty string -> None
                rk2 = rk2 or None  # empty string -> None

                # Create/update the kanji
                kanji = models.Kanji.get(unicode=unicode)
                if kanji is None:
                    # If the kanji was inserted with the wrong unicode
                    # but the right meaning, the above lookup failed,
                    # but we need to update it.
                    kanji = models.Kanji.get(mnemonic_meaning=mnemonic_meaning)
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


def run_cmd_due(args):
    db = models.init(args.database_filename)

    writing_sched = defaultdict(int)
    reading_sched = defaultdict(int)
    meaning_sched = defaultdict(int)
    vocab_sched = defaultdict(int)
    phrase_sched = defaultdict(int)

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
        for result in models.VocabQuizResult.select(user=user):
            vocab_sched[get_days_until_due(result)] += 1
        for result in models.PhraseQuizResult.select(user=user):
            phrase_sched[get_days_until_due(result)] += 1

    # Find the maximum day across all schedules
    max_day = max(
        max(writing_sched.keys(), default=-1),
        max(reading_sched.keys(), default=-1),
        max(meaning_sched.keys(), default=-1),
        max(vocab_sched.keys(), default=-1),
        max(phrase_sched.keys(), default=-1)
    ) + 1  # Add 1 to include the max day in range

    # Truncate to the next two weeks
    max_day = min(max_day, 14)
    
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

    print('  Vocab Due: ', end='')
    for x in range(max_day):
        print(f'{vocab_sched[x]} ', end='')
    print('')

    print('  Phrases Due: ', end='')
    for x in range(max_day):
        print(f'{phrase_sched[x]} ', end='')
    print('')
    

def run_cmd_stats(args):
    db = models.init(args.database_filename)

    with orm.db_session:
        
        user = models.User.get(name=args.username)
        if not user:
            raise UserNotFoundError(f"User with name '{args.username}' not found")

        results = list(models.WritingQuizResult.select(user=user).order_by(
                lambda w: (w.streak, w.last_date)
        ))
        for r in results:
            r.days_until_due = get_days_until_due(r)
        sorted_results = sorted(results, key=lambda r: r.days_until_due)
        for result in sorted_results:
            print(f'{colored(result.kanji.unicode, "cyan", attrs=["bold"])} {result.days_until_due} {colored(result.streak, "green")} {result.last_date}')
            

def run_cmd_roma2hira(args):
    kana, codes = roma2hira(args.roma, return_codes=True)
    print(f'{kana} {",".join(codes)}')


def run_cmd_uni(args):
    for k in args.kanji:
        print(f'{k} {hex(ord(k))}')


def run_review_loop(user, model, limit, test_func, instructions, filter=None):

    # Get due questions
    due = []
    results = model.select(user=user)
    due = [r for r in results if (0 == get_days_until_due(r))]
    if not due:
        cprint(f'{colored("Nothing due", "green")}')
        return 0

    available = len(due)

    if limit:
        # Sort by last review date, most recently reviewed first,
        # before limiting. This facilitates partial review on a huge
        # backlog, allowing the user to build up memory on recently
        # reviewed items before adding new items over future sessions.
        due = sorted(due, key=lambda x: x.last_date, reverse=True)
        due = due[:limit]
    
    # Randomize the list.
    random.shuffle(due)
    total = len(due)
    cprint(f'Reviewing ({total}/{available} cards)', "yellow")
    cprint(instructions, "yellow")
    fails = []

    # Ask the questions and track failures. Update the quiz results.
    for i, qr in enumerate(due):
        try:
            if test_func(qr, i, total):
                qr.streak += 1
                if qr.streak > 0:
                    cprint(f"ok {qr.streak}", "green", attrs=["bold"])
                else:
                    cprint(f"ok {qr.streak}", "yellow", attrs=["bold"])                    
            else:
                if qr.streak > 0:
                    qr.streak = 0
                else:
                    qr.streak -= 1
                fails.append(qr)
            qr.last_date = datetime.now()
        except Exception as e:
            cprint(f"Error in quiz {qr}", "red", attrs=["bold"])
            print(e)
            cprint("Continuing...", "yellow")

    num_correct = total - len(fails)
    percent = round(num_correct * 100 / total)
    cprint(f'You passed {num_correct}/{total} cards ({percent}%)', "green")

    # Review failures.
    while fails:
        failed = len(fails)
        cprint(f"Reviewing failures ({failed} cards)", "yellow")
        refails = []
        for i, qr in enumerate(fails):
            if test_func(qr, i, failed):
                qr.streak += 1
                if qr.streak > 0:
                    cprint(f"ok {qr.streak}", "green", attrs=["bold"])
                else:
                    cprint(f"ok {qr.streak}", "yellow", attrs=["bold"])                
            else:
                refails.append(qr)
                qr.streak -= 1
        fails = refails
    return total


def test_writing(qr, i, total):
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


def test_meaning(qr, i, total):
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


def test_reading(qr, i, total):
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
            on = f'{r}<invalid>'
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


def test_vocab(qr, i, total):
    phrase = qr.phrase

    promptstr = f'({i+1}/{total}) {colored(phrase.unicode, "cyan", attrs=["bold"])}? '

    r = input(promptstr)
    backup = f'\033[1A'
    sys.stdout.write(backup)
    print(f'{promptstr}\b\b ', end='')

    if r:
        try:
            h = roma2hira(r)
        except (KeyError, NotKanaError):
            h = f'{r}<invalid>'
    else:
        h = '?'
    ok = h == phrase.hiragana
    if ok:
        cprint(f'{h} ', "green", end='')

        instr = "meaning? "
        r = input(instr)

        backup = f'\033[1A\033[K'  # move cursor up and clear to end of line
        sys.stdout.write(backup)
        cprint(f'{promptstr}{h} ', end='')

        answers = phrase.meaning.split(";")
        for answer in answers:
            answer = answer.split(' (')[0]  # ignore parenthetical note
            if answer == r:
                cprint(f'{colored(r, "green")} ', end='')
                return True
        cprint(f'{colored(r, "red")} should be {colored(phrase.meaning, "white", attrs=["bold", "underline"])} ', end='')
    else:
        cprint(
            f'{colored(h, "red")} should be {colored(phrase.hiragana, "white", attrs=["bold"])} ({phrase.meaning}) ',
            end=''
        )
    cprint(f"fail", "red", attrs=["bold"])
    return False


def test_phrase(qr, i, total):

    # Hack: test multiple phrases
    #qr = models.PhraseQuizResult.get(hiragana='きかい')
    
    promptstr = f'({i+1}/{total}) {colored(qr.hiragana, "cyan", attrs=["bold"])}? '

    phrases = set(qr.phrases)
    n_phrases = len(phrases)
    
    for i in range(n_phrases):

        r = input(promptstr)
        backup = f'\033[1A'
        sys.stdout.write(backup)
        print(f'{promptstr}\b\b ', end='')

        ok = False

        for phrase in phrases:
        
            answers = phrase.meaning.split(";")
            for answer in answers:
                answer = answer.split(' (')[0]  # ignore parenthetical note
                if answer == r:
                    ok = True
                    break
            if ok:
                cprint(f'{r} ', "green", end='')
                cprint(
                    f'{colored(phrase.meaning, "white", attrs=["bold"])} ({phrase.unicode}) ',
                    end=''
                )
                more = len(phrases) > 1
                if more:
                    cprint('and', "magenta", attrs=["bold"])
                phrases.remove(phrase)
                break

        if not ok:
            # Use the last one found to show one possible meaning
            cprint(
                f'{colored(r, "red")} should be {colored(phrase.meaning, "white", attrs=["bold"])} ({phrase.unicode}) ',
                end=''
            )
            cprint(f"fail", "red", attrs=["bold"])
            return False

    return True


def run_cmd_review(args):
    db = models.init(args.database_filename)
    with orm.db_session:
        user = models.User.get(name=args.username)
        if not user:
            raise UserNotFoundError(f"User with name '{args.username}' not found")

        if args.drillname == 'write':
            run_review_loop(
                user, models.WritingQuizResult, args.limit, test_writing,
                'Given the meaning, write the kanji'
            )
        elif args.drillname == 'mean':
            run_review_loop(
                user, models.MeaningQuizResult, args.limit, test_meaning,
                'Given the kanji, type the meaning'
            )
        elif args.drillname == 'read':
            run_review_loop(
                user, models.ReadingQuizResult, args.limit, test_reading,
                'Given the kanji and the phrase, type the "on" in romaji'
            )
        elif args.drillname == 'vocab':
            run_review_loop(
                user, models.VocabQuizResult, args.limit, test_vocab,
                'Given the phrase, first type the reading in romaji'
            )
        elif args.drillname == 'phrase':
            run_review_loop(
                user, models.PhraseQuizResult, args.limit, test_phrase,
                'Given the hiragana type the meaning'
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
    dump_parser.add_argument(
        '-s', '--specific', choices=('kana', 'kanji', 'phrases', 'readings'),
        default='kanji'
    )
    dump_parser.set_defaults(func=run_cmd_dump)

    stats_parser = subp.add_parser("stats", help="Stats kana and known kanji")
    stats_parser.add_argument(
        '-d', '--drillname', choices=('write', 'read', 'mean', 'vocab'),
        default='write'
    )
    stats_parser.set_defaults(func=run_cmd_stats)

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

    stats_parser = subp.add_parser('due', help="Show drill stats")
    stats_parser.set_defaults(func=run_cmd_due)

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
        '-d', '--drillname', choices=('write', 'read', 'mean', 'vocab', 'phrase'), default='write'
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
