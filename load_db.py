#!/usr/bin/env python

import argparse
import csv
import sqlite3

from kanji import decode, decode_phrase, roma2kata, roma2hira
    

def load_kanji_table(cur, data):
    for e in data:
        try:
            cur.execute(
                "INSERT INTO kanji (unicode, strokes) VALUES(?, ?)",
                (e["kanji_unicode_char"],
                 e["kanji_strokes"])
            )
        except sqlite3.IntegrityError:
            # Probably already loaded. Ignore.
            pass


def load_database(dbname, data):
    con = sqlite3.connect(dbname)
    cur = con.cursor()
    load_kanji_table(cur, data)
    con.commit()
    con.close()


def parse_csv_file(filename):
    """ Read CSV file into flat Python arrays.
    """
    data = []
    with open(filename) as f:
        r = csv.reader(f)
        header = next(r)
        for line in r:
            rk2, unic, mean, strok, on, rk1, phr,phr_kana,phr_eng=line
            unic = decode(unic)
            on = roma2kata(on)
            phr = decode_phrase(phr)
            phr_kana = roma2hira(phr_kana)
            data.append({
                "framev2_4_frame_number": rk2,
                "kanji_unicode_char": unic,
                "framev1_6_meaning": mean,
                "kanji_strokes": strok,
                "framev2_4_kana": on,
                "framev1_6_frame_number": rk1,
                "phrase_kanji_unicode_str": phr,
                "phrase_hiragana": phr_kana,
                "phrase_meaning": phr_eng
            })
    return data
    

if __name__ == "__main__":

    pars = argparse.ArgumentParser(description="Load Sqlite3 database from CSV file")
    pars.add_argument('-d', '--dbname', help="Database name", default='kanji.db')
    pars.add_argument('-f', '--filename', help="CSV filename", default='kanji.csv')

    args = pars.parse_args()
    data = parse_csv_file(args.filename)
    load_database(args.dbname, data)
