#!/usr/bin/env python
import argparse
import csv
import json
import random
import sys, tty, termios
from collections import namedtuple
from datetime import datetime, timedelta
from termcolor import colored, cprint


ROMA2KATA = {
    '_a': '30A1','a': '30A2','_i': '30A3','i': '30A4','_u': '30A5','u': '30A6','_e': '30A7','e': '30A8',
    '_o': '30A9','o': '30AA','ka': '30AB','ga': '30AC','ki': '30AD','gi': '30AE','ku': '30AF','gu': '30B0',
    'ke': '30B1','ge': '30B2','ko': '30B3','go': '30B4','sa': '30B5','za': '30B6','shi': '30B7','ji': '30B8',
    'su': '30B9','zu': '30BA','se': '30BB','ze': '30BC','so': '30BD','zo': '30BE','ta': '30BF','da': '30C0',
    'chi': '30C1','chji': '30C2','_tsu': '30C3', 'tsu': '30C4', 'tzu': '30C5','te': '30C6','de': '30C7','to': '30C8',
    'do': '30C9','na': '30CA','ni': '30CB','nu': '30CC','ne': '30CD','no': '30CE','ha': '30CF','ba': '30D0',
    'pa': '30D1','hi': '30D2','bi': '30D3','pi': '30D4','fu': '30D5','bu': '30D6','pu': '30D7','he': '30D8',
    'be': '30D9','pe': '30DA','ho': '30DB','bo': '30DC','po': '30DD','ma': '30DE','mi': '30DF','mu': '30E0',
    'me': '30E1','mo': '30E2',
    '_ya': '30E3','ya': '30E4','_yu': '30E5','yu': '30E6','_yo': '30E7','yo': '30E8',
    'ra': '30E9','ri': '30EA','ru': '30EB','re': '30EC','ro': '30ED','_wa': '30EE','wa': '30EF', 
    'wo': '30F2', 'n': '30F3',
    'sha': ('shi', '_ya'),
    'shu': ('shi', '_yu'),
    'sho': ('shi', '_yo'),
    'jo': ('ji', '_yo'),
    'cha': ('chi', '_ya'),
    'chu': ('chi', '_yu'),
    'cho': ('chi', '_yo')
}

ROMA2HIRA = {
    'a':  '3042', 'i': '3044', 'u': '3046', 'e': '3048', 'o': '304A',
    'ka': '304B', 'ga': '304C', 'ki': '304D', 'gi': '304E', 'ku': '304F', 'gu': '3050',
    'ke': '3051', 'ge': '3052', 'ko': '3053', 'go': '3054', 'sa': '3055', 'za': '3056', 'shi': '3057', 'ji': '3058',
    'su': '3059', 'zu': '305A', 'se': '305B', 'ze': '305C', 'so': '305D', 'zo': '305E',
    'ta': '305F', 'da': '3060', 'chi': '3061', '_tsu': '3063', 'tsu': '3064', 'dzu': '3065', 'te': '3066', 'de': '3067', 'to': '3068',
    'do': '3069',
    'na': '306A', 'ni': '306B', 'nu': '306C', 'ne': '306D', 'no': '306E', 'ha': '306F', 'ba': '3070',
    'pa': '3071', 'hi': '3072', 'bi': '3073', 'pi': '3074', 'fu': '3075', 'bu': '3076', 'pu': '3077', 'he': '3078',
    'be': '3079', 'po': '307A', 'ho': '307B', 'bo': '307C', 'po': '307D', 'ma': '307E', 'mi': '307F', 'mu': '3080',
    'me': '3081', 'mo': '3082',
    '_ya': '3083', 'ya': '3084', '_yu': '3085', 'yu': '3086', '_yo': '3087', 'yo': '3088',
    'ra': '3089', 'ri': '308A', 'ru': '308B', 're': '308C', 'ro': '308D', 'wa': '308F', 
    'wo': '3092', 'n': '3093',
    'kyo': ('ki', '_yo'),
    'sha': ('shi', '_ya'),
    'shu': ('shi', '_yu'),
    'sho': ('shi', '_yo'), 'jo': ('ji', '_yo'), 'byo': ('bi', '_yo'), 'nyu': ('ni', '_yu'),
    'cha': ('chi', '_ya'),
    'chu': ('chi', '_yu'), 'kyu': ('ki', '_yu'),
    'cho': ('chi', '_yo'),
    'kka': ('_tsu', 'ka'),
    'ppa': ('_tsu', 'pa'), 'ppo': ('_tsu', 'po')
}

# Set up some JSON-serializable data structures to track drill results.
TODAY = datetime.today()
FMT = '%Y-%m-%d'
TODAYSTR = TODAY.strftime(FMT)

class NotKanaError(Exception):

    pass


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
        if len(v) == 3:
            k2m = DrillRecord.load(v[2])
        else:
            k2m = None
        return klass(m2k, p2o, k2m)


class Drill(object):

    def run(self, cards, session, limit=None):
        
        # Count cards due for review. If a card has passed N times, it is
        # due N days from the last day it passed.
        due = []
        for k, r in session.items():
            dr = getattr(r, self.name)
            age = TODAY - datetime.strptime(dr.last, FMT)
            if age.days >= dr.streak:
                due.append((k, dr))

        if not due:
            cprint(f'{colored("Nothing due", "green")}')
            return

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
                cprint(f"fail (R-{card['rk2']})", "red", attrs=["bold"])
                fails.append(card)
            dr.last = TODAYSTR

        cprint(f'You passed {len(due)-len(fails)}/{len(due)} cards', "green")
            
        # Review failures.
        while fails:
            total = len(fails)
            cprint(f"Reviewing failures ({total} cards)", "yellow")
            refails = []
            for i, card in enumerate(fails):
                if not self.review(card, i, total):
                    refails.append(card)
                print()
            fails = refails


class Meaning2KanjiDrill(Drill):

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


class Kanji2MeaningDrill(Drill):

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


class Phrase2OnDrill(Drill):

    name = 'phrase2on'
    instructions = 'Given the kanji and exemplary phrase, type the romaji for the on reading'
    
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
    'p2o': Phrase2OnDrill,
    'm2k': Meaning2KanjiDrill,
    'k2m': Kanji2MeaningDrill
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


def decode(uni):
    return chr(int(uni, 16))


def decode_phrase(phr):
    return "".join(decode(c) for c in phr.split(","))


def convert_roma(phr, code_table, return_codes=False):
    s = ""
    res = []
    codes = []
    saw_n = False  # 'n' requires special handling
    for c in phr:
        if saw_n:
            if c not in 'aeiouy':
                # Must have been terminal 'n'
                code = code_table[s]
                res.append(decode(code))
                codes.append(code)
                s = ""
                saw_n = False
                # My own way to forcibly disambiguate some syllables
                # that end in 'n'
                if c == ':':
                    continue
        s += c
        if s in code_table:
            # Try to handle 'ni' vs 'n'
            if s == 'n':
                saw_n = True
                continue
            saw_n = False
            try:
                code = code_table[s]
                res.append(decode(code))
                codes.append(code)
            except TypeError:
                hira = code_table[s]
                for h in hira:
                    code = code_table[h]
                    res.append(decode(code))
                    codes.append(code)
            s = ""
    if s:
        if saw_n:
            # Must have been terminal 'n' at the end
            code = code_table[s]
            res.append(decode(code))
            codes.append(code)
        else:
            raise NotKanaError(f'{s} is not kana')
    hira = "".join(res)
    if return_codes:
        return hira, codes
    else:
        return hira


def roma2kata(s):
    return convert_roma(s, ROMA2KATA)


def roma2hira(phr, **kwargs):
    return convert_roma(phr, ROMA2HIRA, **kwargs)


def load_cards(filename):
    data = {}
    with open(filename) as f:
        r = csv.reader(f)
        header = next(r)
        for line in r:
            rk2, unic, mean, strok, on, rk1, phr,phr_kana,phr_eng=line
            unic = decode(unic)
            on = roma2kata(on)
            phr = decode_phrase(phr)
            phr_kana = roma2hira(phr_kana)
            data[rk2] = {
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
    phr = d["phrase"]["kanji"]
    phr_kana = d["phrase"]["kana"]
    phr_eng =  d["phrase"]["meaning"]
    try:
        print(f'{d["rk2"]:<4} {d["unicode"]} {d["meaning"]:12} {d["on"]:<6}  {phr:<6} {phr_kana:6} {phr_eng}')
    except:
        print(d)

    
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


def save_session(session, filename):
    # Save results.
    for k, cr in session.items():
        session[k] = cr.save()
    with open(filename, 'w') as f:
        json.dump(session, f)


def review(args):
    cards = load_cards(args.kanji)
    session = load_session(args.record)
    
    # Add any new cards added since the last session.
    for k in cards.keys():
        if k not in session:
            session[k] = CardRecord()

    drill = DRILL_CLASSES[args.drillname]()
    drill.run(cards, session, args.limit)
    save_session(session, args.record)


def stats(args):
    cards = load_cards(args.kanji)
    session = load_session(args.record)
    for k, r in session.items():
        attrs = []
        if r.meaning2kanji.streak and r.phrase2on.streak:
            if r.meaning2kanji.streak >= 5 and r.phrase2on.streak >= 5:
                color = "green"
                attrs.append("bold")
            elif r.meaning2kanji.streak >= 3 and r.phrase2on.streak >= 3:
                color = "green"
            else:
                color = "yellow"
        else:
            color = "red"
        cprint(f'{cards[k]["unicode"]} {r.meaning2kanji.streak} {r.meaning2kanji.last} {r.phrase2on.streak} {r.phrase2on.last} {cards[k]["on"]}', color, attrs=attrs)
    
    
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
    cmdp.add_argument('-d', '--drillname', choices=('m2k', 'p2o', 'k2m'), default='m2k')
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
