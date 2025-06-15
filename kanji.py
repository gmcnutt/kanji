#!/usr/bin/env python
import argparse
import csv
import json
import math
import random
import sys, tty, termios
from datetime import datetime, timedelta
from termcolor import colored, cprint

from kana import decode, decode_phrase, roma2kata, roma2hira, NotKanaError

AGE_FACTOR = 1.6
TODAY = datetime.today()
FMT = '%Y-%m-%d'
TODAYSTR = TODAY.strftime(FMT)


def build_kanji_table(cards):
    # FIXME: obsolete?
    table = {}
    for pk, card in cards.items():
        kanji = card["unicode"]
        table[kanji] = card
    return table


class DrillRecord(object):
    """Track drill results for a single question."""
    def __init__(self, streak=0, last=TODAYSTR):
        self.streak = streak
        self.last = last

    def save(self):
        return (self.streak, self.last)

    @classmethod
    def load(klass, v):
        return DrillRecord(*v)

    def get_days_until_due(self):
        """Return the number of days until the next review."""
        age = TODAY - datetime.strptime(self.last, FMT)
        days_to_wait = math.ceil(self.streak * AGE_FACTOR)
        days_until_due = days_to_wait - age.days
        return max(0, days_until_due)


class CardRecord(object):
    """Track all types of drill results for a single card."""
    def __init__(self, m2k=None, p2o=None, k2m=None):
        self.meaning2kanji=m2k or DrillRecord()
        self.phrase2on = p2o or DrillRecord()
        self.kanji2meaning = k2m or DrillRecord()

    def save(self):
        return [
            self.meaning2kanji.save(),
            self.phrase2on.save(),
            self.kanji2meaning.save()
        ]

    @classmethod
    def load(klass, v):
        m2k = DrillRecord.load(v[0])
        p2o = DrillRecord.load(v[1])
        k2m = DrillRecord.load(v[2])
        return klass(m2k, p2o, k2m)


class Drill(object):
    """General question/answer drill framework."""
    def get_due(self, session):
        return session.get_due(self.drillname)

    def filter_due(self, due, cards):
        return due

    def run(self, cards, session, limit=None):

        # Count cards due for review. If a card has passed N times, it is
        # due N days from the last day it passed.
        due = self.get_due(session)
        due = self.filter_due(due, cards)

        if not due:
            cprint(f'{colored("Nothing due", "green")}')
            return 0

        # Review the cards in random order, remembering the fails for
        # review below.
        random.shuffle(due)
        available = len(due)
        if limit:
            due = due[:limit]
        total = len(due)
        cprint(f'Reviewing ({total}/{available} cards)', "yellow")
        cprint(self.instructions, "yellow")
        fails = []

        for i, (k, dr) in enumerate(due):
            card = cards[k]
            if self.review(card, i, total):
                dr.streak += 1
                cprint(f"ok {dr.streak}x", "green", attrs=["bold"])
            else:
                dr.streak = 0
                cprint(f"fail (R-{card['rk2']}/{card['rk1']})", "red",
                       attrs=["bold"])
                fails.append(card)
            dr.last = TODAYSTR

        num_correct = total - len(fails)
        percent = round(num_correct * 100 / total)
        cprint(f'You passed {num_correct}/{total} cards ({percent}%)', "green")

        # Review failures.
        while fails:
            failed = len(fails)
            cprint(f"Reviewing failures ({failed} cards)", "yellow")
            refails = []
            for i, card in enumerate(fails):
                if not self.review(card, i, failed):
                    refails.append(card)
                print()
            fails = refails
        return total


class WritingDrill(Drill):

    name = 'meaning2kanji'
    drillname = 'writing'
    instructions = 'Given the meaning, write the kanji'

    def review(self, card, i, total):
        instr1 = '<Press any key to check>'
        instr2 = 'correct? <y/n>'
        prompt(f'({i+1}/{total}) {colored(card["meaning"], attrs=["bold"]):16} {colored(instr1, "yellow")}')
        backspace(instr1)
        ok = prompt(f' {colored(card["unicode"],"cyan", attrs=["bold"])} ({card["strokes"]}) {colored(instr2, "yellow")}')
        backspace(instr2)
        return ok == 'y'


class MeaningDrill(Drill):

    name = 'kanji2meaning'
    drillname = 'meaning'
    instructions = 'Given the kanji, write the meaning'

    def review(self, card, i, total):
        promptstr = f'({i+1}/{total}) {colored(card["unicode"], "cyan", attrs=["bold"])}? '
        r = input(promptstr)

        backup = f'\033[1A'
        sys.stdout.write(backup)
        print(f'{promptstr}{r} ', end='')

        ok = r == card["meaning"]
        if not ok:
            print(f'should be {colored(card["meaning"], "red", attrs=["underline"])} ', end='')
        return ok


class OnDrill(Drill):

    name = 'phrase2on'
    drillname = 'on'
    instructions = 'Given the kanji and exemplary phrase, type the romaji for the on reading'

    def filter_due(self, due, cards):
        """Remove any cards that have no 'on' reading."""
        filtered = []
        for (k, r) in due:
            card = cards[k]
            if card['on'] is not None:
                filtered.append((k, r))
        return filtered

    def review(self, card, i, total):
        promptstr = f'({i+1}/{total}) {colored(card["unicode"], "cyan", attrs=["bold"])} in {colored(card["phrase"]["kanji"], "cyan")}? '
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
        ok = on == card["on"]
        if ok:
            cprint(f'{on} ', "green", end='')
        else:
            print(f'{colored(on, "red")} should be {card["on"]} ', end='')
        print(f'in {colored(card["phrase"]["kana"], "light_grey")} ({card["phrase"]["meaning"]}) ', end='')
        return ok


DRILL_CLASSES = {
    'on': OnDrill,
    'write': WritingDrill,
    'mean': MeaningDrill,
}


def print_range(title, start, end):
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


def load_cards(filename):
    data = {}
    with open(filename) as f:
        r = csv.reader(f)
        header = next(r)
        for line in r:
            pk, rk2, unic, mean, strok, on, rk1, phr,phr_kana,phr_eng=line
            unic = decode(unic)
            on = roma2kata(on) or None
            phr = decode_phrase(phr) if phr else None
            phr_kana = roma2hira(phr_kana)
            data[pk] = {
                "rk2": rk2,
                "unicode": unic,
                "meaning": mean,
                "strokes": strok,
                "on": on,
                "rk1": rk1,
                "phrase": {
                    "kanji": phr,
                    "kana": phr_kana,
                    "meaning": phr_eng
                }
            }
        return data


def dump_entry(d):
    phr = d["phrase"]["kanji"] or '-'
    phr_kana = d["phrase"]["kana"] or '-'
    phr_eng =  d["phrase"]["meaning"] or '-'
    on = d["on"] or '-'
    print(f'{d["rk2"]:<4} {d["unicode"]} {d["meaning"]:12} {on:<6}  {phr:<6} {phr_kana:6} {phr_eng}')


def dump_csv(filename):
    data = load_cards(filename)
    for d in data.values():
        dump_entry(d)


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


def review_card(card):
    instr1 = '<Write kanji on paper then press any key>'
    instr2 = 'correct? <y/n>'
    instr3 = '<Write "on" reading on paper then press any key>'
    prompt(f'{colored(card["meaning"], attrs=["bold"]):16} {colored(instr1, "yellow")}')
    backspace(instr1)
    ok = prompt(f' {colored(card["unicode"], "cyan", attrs=["bold"])} {colored(instr2, "yellow")}')
    backspace(instr2)
    if ok != 'y':
        return False

    prompt(f'{colored(instr3, "yellow")}')
    backspace(instr3)
    ok = prompt(f' {colored(card["on"], "cyan", attrs=["bold"])} {colored(instr2, "yellow")}')
    backspace(instr2)
    if ok != 'y':
        return False
    return True


class Session(object):

    def __init__(self, data=None):
        self.data = data or {}

    def get_due(self, drillname):
        due = []
        attr = {
            "writing": "meaning2kanji",
            "on": "phrase2on",
            "meaning": "kanji2meaning"
        }[drillname]
        for k, card_record in self.data.items():
            drill_record = getattr(card_record, attr)
            if 0 == drill_record.get_days_until_due():
                due.append((k, drill_record))
        return due

    def get_records(self, drillname):
        records = []
        attr = {
            "writing": "meaning2kanji",
            "on": "phrase2on",
            "meaning": "kanji2meaning"
        }[drillname]
        for k, record in self.data.items():
            records.append(getattr(record, attr))
        return records


    @classmethod
    def load(klass, filename):
        """Load session from a JSON file."""
        # Load raw values as a dict.
        try:
            with open(filename) as f:
                data = json.load(f)
        except:
            data = {}

        # Convert raw values to CardRecord objects.
        for k, v in data.items():
            data[k] = CardRecord.load(v)

        return klass(data)

    def update(self, cards):
        """Add any new cards added since the last session."""
        for k in cards.keys():
            if k not in self.data:
                self.data[k] = CardRecord()

    def save(self, filename):
        """Save results as a JSON file."""
        to_save = {}
        for k, cr in self.data.items():
            to_save[k] = cr.save()
        with open(filename, 'w') as f:
            json.dump(to_save, f)


def run_cmd_dump(args):
    print_range("---hiragana---", 0x3041, 0x3096)
    print_range("---katakana---", 0x30a1, 0x30fa)
    dump_csv(args.kanji)


def run_cmd_review(args):
    cards = load_cards(args.kanji)
    session = Session.load(args.record)
    session.update(cards)

    drill = DRILL_CLASSES[args.drillname]()
    start = datetime.now()
    num_cards = drill.run(cards, session, args.limit)
    if not num_cards:
        return
    end = datetime.now()
    session.save(args.record)

    duration = (end - start)
    sec_per_card = duration.seconds/num_cards
    print(f'{duration}--{sec_per_card} seconds per card')


def run_cmd_stats(args):
    """
    Print a table. Rows indicate correct writing, columns correct phrasing.
    """
    cards = load_cards(args.kanji)
    session = Session.load(args.record)
    session.update(cards)
    N = 30
    writing_sched = [0 for x in range(N)]
    reading_sched = [0 for x in range(N)]
    meaning_sched = [0 for x in range(N)]

    for record in session.get_records("writing"):
        writing_sched[record.get_days_until_due()] += 1
    for record in session.get_records("on"):
        reading_sched[record.get_days_until_due()] += 1
    for record in session.get_records("meaning"):
        meaning_sched[record.get_days_until_due()] += 1

    print('Writing Due: ', end='')
    for x in range(N):
        print(f'{writing_sched[x]} ', end='')
    print('')

    print('     On Due: ', end='')
    for x in range(N):
        print(f'{reading_sched[x]} ', end='')
    print('')

    print('Meaning Due: ', end='')
    for x in range(N):
        print(f'{meaning_sched[x]} ', end='')
    print('')


def run_cmd_roma(args):
    kana, codes = roma2hira(args.hira, return_codes=True)
    print(f'{kana} {",".join(codes)}')


def run_cmd_uni(args):
    for k in args.kanji:
        print(f'{k} {hex(ord(k))}')


if __name__ == "__main__":
    pars = argparse.ArgumentParser(description="Kanji Tools")
    pars.add_argument('-k', '--kanji', help="Kanji CSV file to load", default="kanji.csv")
    pars.add_argument('-r', '--record',  help="Record file for tracking history", default="review.json")

    subp = pars.add_subparsers(help="Commands", required=True)

    dump_parser = subp.add_parser('dump', help="Dump kana and known kanji")
    dump_parser.set_defaults(func=run_cmd_dump)

    stats_parser = subp.add_parser('stats', help="Show drill stats")
    stats_parser.set_defaults(func=run_cmd_stats)

    review_parser = subp.add_parser('review', help="Review cards that are due")
    review_parser.add_argument('-d', '--drillname', choices=('write', 'on', 'mean'), default='write')
    review_parser.add_argument('-l', '--limit', type=int, default=None, help='Limit the number of cards to review')
    review_parser.set_defaults(func=run_cmd_review)

    roma_parser = subp.add_parser('roma', help="Convert romaji to hiragana")
    roma_parser.add_argument('hira')
    roma_parser.set_defaults(func=run_cmd_roma)

    uni_parser = subp.add_parser('uni', help="Show the unicode for a character or list of characters")
    uni_parser.add_argument('kanji')
    uni_parser.set_defaults(func=run_cmd_uni)

    args = pars.parse_args()
    args.func(args)
