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

def dump_csv():
    with open("kanji.csv") as f:
        r = csv.reader(f)
        header = next(r)
        for line in r:
            rk2, unic, mean, strok, on, rk1, phr,phr_kana,phr_eng=line
            unic = decode(unic)
            on = decode(on)
            phr = decode_phrase(phr)
            phr_kana = decode_phrase(phr_kana)
            print(f'{rk2:<2} {unic} {mean:12} {on}  {phr:<6} {phr_kana:6} {phr_eng}')

def dump():
    print_range("---hiragana---", 0x3041, 0x3096)
    print_range("---katakana---", 0x30a1, 0x30fa)
    dump_csv()

dump_csv()
