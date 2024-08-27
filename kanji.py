#!/usr/bin/env python
import argparse
import csv
import sys, tty, termios
from termcolor import colored, cprint


ROMA2KATA = {
    'sa': '30b5',
    'se': '30bb',
    'ta': '30bf',
    'chi': '30c1',
    'ni': '30cb',
    'fu': '30d5',
    'mi': '30df',
    'me': '30e1',
    'ri': '30ea',
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
            phr_kana = decode_phrase(phr_kana)
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
    print(f'{d["rk2"]:<2} {d["unicode"]} {d["meaning"]:12} {d["on"]}  {phr:<6} {phr_kana:6} {phr_eng}')

    
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
