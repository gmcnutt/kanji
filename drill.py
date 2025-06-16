#!/usr/bin/env python

import argparse
import csv
from pony import orm

import models
from kana import decode, decode_phrase, roma2kata, roma2hira, NotKanaError


@orm.db_session
def load_kanji_and_phrases_from_csv(db, filename):
    """Create the kanji and phrase objects from the CSV file.

    These are persisted to the database. This only needs to be done
    when changes are made to the CSV file or if the database has been
    newly created. It is safe to run anytime, however.

    """
    data = {}
    with open(filename) as f:
        r = csv.reader(f)
        header = next(r)
        for line in r:
            (pk, rk2, unicode, mnemonic_meaning, stroke_count, on,
             heisig_v1_frame, phr,phr_kana,phr_eng) = line
            unicode = decode(unicode)
            on = roma2kata(on) or None
            phr = decode_phrase(phr) if phr else None
            phr_kana = roma2hira(phr_kana)

            # If the kanji has not been created yet...
            kanji = models.Kanji.get(unicode=unicode)
            if kanji is None:
                # Create it now
                models.Kanji(
                    unicode=unicode,
                    mnemonic_meaning=mnemonic_meaning,
                    heisig_v1_frame=heisig_v1_frame,
                    stroke_count=stroke_count
                )
            else:
                # Else ensure it is up to date
                kanji.unicode = unicode
                kanji.mnemonic_meaning = mnemonic_meaning
                kanji.heisig_v1_frame = heisig_v1_frame
                kanji.stroke_count = stroke_count

            # If the reading has not been created yet...
                    

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
    dump_unicode_range("---hiragana---", 0x3041, 0x3096)
    dump_unicode_range("---katakana---", 0x30a1, 0x30fa)
    db = models.init(args.database_filename)
    load_kanji_and_phrases_from_csv(db, args.kanji)
    print("---kanji---")
    with orm.db_session:
        kanjis = models.Kanji.select()
        for kanji in kanjis:
            print(f'{kanji.unicode} {kanji.mnemonic_meaning:16} R1-{kanji.heisig_v1_frame}')


if __name__ == "__main__":

    pars = argparse.ArgumentParser(description="Kanji Learning Drills")
    pars.add_argument('-k', '--kanji', help="CSV file with kanji data to load", default="kanji.csv")
    # pars.add_argument('-r', '--record',  help="Record file with quiz result history", default="review.json")

    subp = pars.add_subparsers(help="Commands", required=True)

    dump_parser = subp.add_parser("dump", help="Dump kana and known kanji")
    dump_parser.add_argument("-db", "--database_filename", help="Database file", default="kanji_db.sql")
    dump_parser.set_defaults(func=run_cmd_dump)

    # stats_parser = subp.add_parser('stats', help="Show drill stats")
    # stats_parser.set_defaults(func=run_cmd_stats)

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
    args.func(args)
