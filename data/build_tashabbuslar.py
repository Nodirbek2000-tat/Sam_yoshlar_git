# -*- coding: utf-8 -*-
"""Tashabbuslar import faylini yig'adi.

    python data/build_tashabbuslar.py

Natija: data/tashabbuslar.json — panel > JSON import ga yuklanadi.
"""
import io
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, 'parts'))

import p1, p2, p3, p4  # noqa: E402

# Yo'nalishlar ketma-ketligi — saytdagi tartib bilan bir xil
ORDER = ['eco', 'fintech', 'ai', 'edu', 'social', 'agro', 'energy',
         'industry', 'startup', 'creative', 'culture', 'smartcity',
         'science', 'water']

FIELDS = ('kind', 'title', 'description', 'expected_result',
          'author_name', 'author_phone', 'region', 'vote_count',
          'created_at', 'comments')


def collect():
    rows = {}
    for module in (p1, p2, p3, p4):
        for direction, items in module.ROWS.items():
            if direction in rows:
                raise SystemExit(f"'{direction}' ikki marta e'lon qilingan")
            rows[direction] = items
    return rows


def main():
    rows = collect()

    missing = [d for d in ORDER if d not in rows]
    extra = [d for d in rows if d not in ORDER]
    if missing:
        raise SystemExit(f"yo'nalish yetishmayapti: {missing}")
    if extra:
        raise SystemExit(f"noma'lum yo'nalish: {extra}")

    initiatives = []
    for direction in ORDER:
        for row in rows[direction]:
            if len(row) != len(FIELDS):
                raise SystemExit(f"{direction}: «{row[1]}» — maydonlar soni {len(row)}")
            item = dict(zip(FIELDS, row))
            item['comments'] = [
                {'author_name': a, 'text': t, 'created_at': d}
                for a, t, d in item['comments']
            ]
            item['direction'] = direction
            initiatives.append(item)

    out = os.path.join(BASE, 'tashabbuslar.json')
    with io.open(out, 'w', encoding='utf-8') as fh:
        json.dump({'initiatives': initiatives}, fh,
                  ensure_ascii=False, indent=2)

    votes = sum(i['vote_count'] for i in initiatives)
    comments = sum(len(i['comments']) for i in initiatives)
    size = os.path.getsize(out) / 1024

    print(f"{out}")
    print(f"  yo'nalish : {len(ORDER)}")
    print(f"  tashabbus : {len(initiatives)}")
    print(f"  izoh      : {comments}")
    print(f"  ovoz      : {votes}")
    print(f"  hajm      : {size:.0f} KB")
    print()
    for direction in ORDER:
        items = [i for i in initiatives if i['direction'] == direction]
        v = [i['vote_count'] for i in items]
        print(f"  {direction:<10} {len(items):>3} ta   ovoz {min(v):>3}..{max(v):<4} jami {sum(v)}")


if __name__ == '__main__':
    main()
