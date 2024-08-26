#!/usr/bin/env python
import argparse
import csv


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

def load_data():
    data = []
    with open("kanji.csv") as f:
        r = csv.reader(f)
        header = next(r)
        for line in r:
            rk2, unic, mean, strok, on, rk1, phr,phr_kana,phr_eng=line
            unic = decode(unic)
            on = decode(on)
            phr = decode_phrase(phr)
            phr_kana = decode_phrase(phr_kana)
            data.append({
                "rk2": rk2,
                "unicode": unic,
                "meaning": mean,
                "strokes": strok,
                "on": on,
                "rk1": rk1,
                "exemplary_phrase": {
                    "phrase": phr,
                    "kana": phr_kana,
                    "meaning": phr_eng
                }
            })
        return data
            
def dump_csv():
    data = load_data()
    for d in data:
        phr = d["exemplary_phrase"]["phrase"]
        phr_kana = d["exemplary_phrase"]["kana"]
        phr_eng =  d["exemplary_phrase"]["meaning"]
        print(f'{d["rk2"]:<2} {d["unicode"]} {d["meaning"]:12} {d["on"]}  {phr:<6} {phr_kana:6} {phr_eng}')

def dump():
    print_range("---hiragana---", 0x3041, 0x3096)
    print_range("---katakana---", 0x30a1, 0x30fa)
    dump_csv()

def rtk1():
    print("Drill")
    
if __name__ == "__main__":
    pars = argparse.ArgumentParser(description="Kanji Tools")
    subp = pars.add_subparsers(help="Commands", required=True)

    cmdp = subp.add_parser('dump', help="Dump kana and known kanji")
    cmdp.set_defaults(func=dump)

    cmdp = subp.add_parser('rtk1', help="Drill Remembering the Kanji I")
    cmdp.set_defaults(func=rtk1)
    
    args = pars.parse_args()
    args.func()
