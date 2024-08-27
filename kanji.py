#!/usr/bin/env python
import argparse
import csv
import sys, tty, termios
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
    'me': '30E1','mo': '30E2','_ya': '30E3','ya': '30E4','_yu': '30E5','yu': '30E6','_yo': '30E7','yo': '30E8',
    'ra': '30E9','ri': '30EA','ru': '30EB','re': '30EC','ro': '30ED','_wa': '30EE','wa': '30EF', 
    'wo': '30F2',
}

ROMA2HIRA = {
    'a':  '3042', 'i': '3044', 'u': '3046', 'e': '3048', 'o': '304A',
    'ka': '304B', 'ga': '304C', 'ki': '304D', 'gi': '304E', 'ku': '304F', 'gu': '3050',
    'ke': '3051', 'ge': '3052', 'ko': '3053', 'go': '3054', 'sa': '3055', 'za': '3056', 'shi': '3057', 'ji': '3058',
    'su': '3059', 'zu': '305A', 'se': '305B', 'ze': '305C', 'so': '305D', 'zo': '305E', 'ta': '305F', 'ta': '3060',
    'chi': '3061', 'tsu': '3064', 'dzu': '3065', 'te': '3066', 'de': '3067', 'to': '3068',
    'do': '3069', 'na': '306A', 'ni': '306B', 'nu': '306C', 'ne': '306D', 'no': '306E', 'ha': '306F', 'ba': '3070',
    'po': '3071', 'hi': '3072', 'bi': '3073', 'pi': '3074', 'fu': '3075', 'bu': '3076', 'pu': '3077', 'he': '3078',
    'be': '3079', 'po': '307A', 'ha': '307B', 'ba': '307C', 'pa': '307D', 'ma': '307E', 'mi': '307F', 'mu': '3080',
    'me': '3081', 'mo': '3082', 'ya': '3084', 'yu': '3086', 'yo': '3088',
    'ra': '3089', 'ri': '308A', 'ru': '308B', 're': '308C', 'ro': '308D', 'wa': '308F', 
    'wo': '3092', 'n': '3093',
    'sho': ('3057', '3087'), 'jo': ('3058', '3087'),
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


def roma2kata(s):
    return decode(ROMA2KATA[s])


def roma2hira(phr):
    s = ""
    res = []
    for c in phr:
        s += c
        if s in ROMA2HIRA:
            # Try to handle 'ni' vs 'n'
            if s == 'n' and not res:
                continue
            try:
                res.append(decode(ROMA2HIRA[s]))
            except TypeError:
                hira = ROMA2HIRA[s]
                for h in hira:
                    res.append(decode(h))
            s = ""
    if s:
        raise Exception(f'{s} is not hiragana')
    return "".join(res)


def load_data():
    data = []
    with open("kanji.csv") as f:
        r = csv.reader(f)
        header = next(r)
        for line in r:
            rk2, unic, mean, strok, on, rk1, phr,phr_kana,phr_eng=line
            unic = decode(unic)
            on = roma2kata(on)
            phr = decode_phrase(phr)
            phr_kana = roma2hira(phr_kana)
            data.append({
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
            })
        return data

    
def dump_entry(d):
    phr = d["phrase"]["kanji"]
    phr_kana = d["phrase"]["kana"]
    phr_eng =  d["phrase"]["meaning"]
    try:
        print(f'{d["rk2"]:<2} {d["unicode"]} {d["meaning"]:12} {d["on"]}  {phr:<6} {phr_kana:6} {phr_eng}')
    except:
        print(d)

    
def dump_csv():
    data = load_data()
    for d in data:
        dump_entry(d)


def dump():
    print_range("---hiragana---", 0x3041, 0x3096)
    print_range("---katakana---", 0x30a1, 0x30fa)
    dump_csv()


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


def rtk1():
    data = load_data()
    print("Write the kanji for the given meaning then hit <Enter>...")
    instr1 = '<Press any key to check>'
    instr2 = 'correct? <y/n>'
    for d in data[:2]:
        prompt(f'{colored(d["meaning"], attrs=["bold"]):16} {colored(instr1, "yellow")}')
        backspace(instr1)
        ok = prompt(f' {colored(d["unicode"], "cyan", attrs=["bold"])} {colored(instr2, "yellow")}')
        backspace(instr2)
        if ok == 'y':
            cprint("ok", "green", attrs=["bold"])
        else:
            cprint("fail", "red", attrs=["bold"])

def add():
    data = load_data()
    instr2 = 'correct? <y/n>'

    while True:
        entry = {}

        index = len(data)
        print(f'R-{index}')
        entry["rk2"] = index

        entry["unicode"] = decode(input("Unicode: "))
        entry["meaning"] = input("Meaning: ")
        entry["strokes"] = input("Strokes: ")
        entry["on"] = input("on: ")
        entry["rk1"] = input("rk1: ")
        entry["phrase"] = {}
        entry["phrase"]["kanji"] = decode_phrase(input("Phrase kanji: "))
        entry["phrase"]["kana"] = input("Phrase kana: ")
        entry["phrase"]["meaning"] = input("Phrase meaning: ")
        dump_entry(entry)

        ok = prompt(f'{colored(instr2, "yellow")}')
        backspace(instr2)
        if ok == 'y':
            cprint("Added", "green", attrs=["bold"])
            data.append(entry)
        else:
            cprint("Discarded", "red", attrs=["bold"])
    
    
    

            
if __name__ == "__main__":
    pars = argparse.ArgumentParser(description="Kanji Tools")
    subp = pars.add_subparsers(help="Commands", required=True)

    cmdp = subp.add_parser('dump', help="Dump kana and known kanji")
    cmdp.set_defaults(func=dump)

    cmdp = subp.add_parser('rtk1', help="Drill Remembering the Kanji I")
    cmdp.set_defaults(func=rtk1)

    cmdp = subp.add_parser('add', help="Add more kanji")
    cmdp.set_defaults(func=add)
    
    args = pars.parse_args()
    args.func()
