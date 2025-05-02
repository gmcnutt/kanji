#!/usr/bin/env python
import argparse
import csv
import json
import math
import random
import sys, tty, termios
from datetime import datetime, timedelta
from termcolor import colored, cprint

from roma import decode, decode_phrase, roma2kata, roma2hira, NotKanaError

AGE_FACTOR = 1.6


# Set up some JSON-serializable data structures to track drill results.
TODAY = datetime.today()
FMT = '%Y-%m-%d'
TODAYSTR = TODAY.strftime(FMT)

class DrillRecord(object):

    def __init__(self, streak=0, last=TODAYSTR):
        self.streak = streak
        self.last = last

    def save(self):
        return (self.streak, self.last)

    @classmethod
    def load(klass, v):
        return DrillRecord(*v)


class CardRecord(object):

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

    def get_due(self, session):
        due = []
        for k, r in session.items():
            dr = getattr(r, self.name)
            age = TODAY - datetime.strptime(dr.last, FMT)
            if age.days >= (AGE_FACTOR * dr.streak):
                due.append((k, dr))
        return due

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
                cprint(f"fail (R-{card['rk2']}/{card['rk1']})", "red", attrs=["bold"])
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


class WriteKanjiDrill(Drill):

    name = 'meaning2kanji'
    instructions = 'Given the meaning, write the kanji'

    def review(self, card, i, total):
        instr1 = '<Press any key to check>'
        instr2 = 'correct? <y/n>'
        prompt(f'({i+1}/{total}) {colored(card["meaning"], attrs=["bold"]):16} {colored(instr1, "yellow")}')
        backspace(instr1)
        ok = prompt(f' {colored(card["unicode"], "cyan", attrs=["bold"])} ({card["strokes"]}) {colored(instr2, "yellow")}')
        backspace(instr2)
        return ok == 'y'


class TypeMeaningDrill(Drill):

    name = 'kanji2meaning'
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
    'write': WriteKanjiDrill,
    'mean': TypeMeaningDrill
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


def dump(args):
    print_range("---hiragana---", 0x3041, 0x3096)
    print_range("---katakana---", 0x30a1, 0x30fa)
    dump_csv(args.kanji)


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

def load_session(filename):
    # Load past session. A session is a dict where the keys are
    # indices into the 'cards' array and the values are CardRecords.
    try:
        with open(filename) as f:
            session = json.load(f)
    except:
        session = {}
    for k, v in session.items():
        session[k] = CardRecord.load(v)
    return session


def update_session(session, cards):
    # Add any new cards added since the last session.
    for k in cards.keys():
        if k not in session:
            session[k] = CardRecord()
    

def save_session(session, filename):
    # Save results.
    for k, cr in session.items():
        session[k] = cr.save()
    with open(filename, 'w') as f:
        json.dump(session, f)


def review(args):
    cards = load_cards(args.kanji)
    session = load_session(args.record)
    update_session(session, cards)

    drill = DRILL_CLASSES[args.drillname]()
    start = datetime.now()
    num_cards = drill.run(cards, session, args.limit)
    if not num_cards:
        return
    end = datetime.now()
    save_session(session, args.record)

    duration = (end - start)
    sec_per_card = duration.seconds/num_cards
    print(f'{duration}--{sec_per_card} seconds per card')


def stats(args):
    """
    Print a table. Rows indicate correct writing, columns correct phrasing.
    """
    cards = load_cards(args.kanji)
    session = load_session(args.record)
    update_session(session, cards)
    N = 30
    writing_sched = [0 for x in range(N)]
    reading_sched = [0 for x in range(N)]
    meaning_sched = [0 for x in range(N)]

    drill = WriteKanjiDrill()

    def get_due(record):
        age = TODAY - datetime.strptime(record.last, FMT)
        days_to_wait = math.ceil(record.streak * AGE_FACTOR)
        days_until_due = days_to_wait - age.days
        return max(0, days_until_due)

    for k, r in session.items():
        card = cards[k]
        writing_sched[get_due(r.meaning2kanji)] += 1
        if card['on'] is not None:
            reading_sched[get_due(r.phrase2on)] += 1
        meaning_sched[get_due(r.kanji2meaning)] += 1
        
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


def roma(args):
    kana, codes = roma2hira(args.hira, return_codes=True)
    print(f'{kana} {",".join(codes)}')


def kanji2unicode(args):
    for k in args.kanji:
        print(f'{k} {hex(ord(k))}')


if __name__ == "__main__":
    pars = argparse.ArgumentParser(description="Kanji Tools")
    pars.add_argument('-k', '--kanji', help="Kanji CSV file to load", default="kanji.csv")
    pars.add_argument('-r', '--record',  help="Record file for tracking history", default="review.json")

    subp = pars.add_subparsers(help="Commands", required=True)
    
    cmdp = subp.add_parser('dump', help="Dump kana and known kanji")
    cmdp.set_defaults(func=dump)

    cmdp = subp.add_parser('stats', help="Show drill stats")
    cmdp.set_defaults(func=stats)
    
    cmdp = subp.add_parser('review', help="Drill Remembering the Kanji I")
    cmdp.add_argument('-d', '--drillname', choices=('write', 'on', 'mean'), default='write')
    cmdp.add_argument('-l', '--limit', type=int, default=None, help='Limit the number of cards to review')

    cmdp.set_defaults(func=review)

    cmdp = subp.add_parser('roma', help="Convert romaji to hiragana")
    cmdp.add_argument('hira')
    cmdp.set_defaults(func=roma)

    cmdp = subp.add_parser('uni', help="Show the unicode for a character or list of characters")
    cmdp.add_argument('kanji')
    cmdp.set_defaults(func=kanji2unicode)
    
    args = pars.parse_args()
    args.func(args)
