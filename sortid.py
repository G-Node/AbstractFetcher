#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import codecs
import sys
import csv

from difflib import SequenceMatcher

from gca.core import Abstract, Conference


def sanitize_title(title):
    return title.strip(' "\n')


def main():
    parser = argparse.ArgumentParser(description='GCA Linter')
    parser.add_argument('abstracts', type=str, default='-')
    parser.add_argument('sortids')
    parser.add_argument('conference')
    args = parser.parse_args()

    fn = args.abstracts
    fd = codecs.open(fn, 'r', encoding='utf-8') if fn != '-' else sys.stdin
    fc = codecs.open(args.conference, encoding='utf-8')

    conference = Conference.from_data(fc.read())

    titles = {}
    with open(args.sortids, 'rb') as cf:
        header = True
        reader = csv.reader(cf, delimiter=';', quotechar="\"")
        for row in reader:
            if header:
                header = False
                continue
            aid = sanitize_title(row[0])
            title = sanitize_title(row[1].decode('utf-8'))
            titles[title] = aid

    abstracts = Abstract.from_data(fd.read())
    amap = {a.uuid: a for a in abstracts}

    t1 = sorted([(t, k) for t, k in titles.viewitems()])
    t2 = sorted([(a.title, a.uuid) for a in abstracts])

    i = j = 0

    missing = []
    matches = {}

    while i < len(t1) and j < len(t2):
        x, y = t1[i], t2[j]
        a, b = x[0].lower(), y[0].lower()

        skey = x[1]
        uuid = y[1]

        s = SequenceMatcher(lambda x: x == " ", a, b)
        r = round(s.ratio(), 3)

        if r > 0.9:
            i += 1
            j += 1
            matches[uuid] = skey
            print("%.10s -> %.10s [%.3f]" % (a, b, r), file=sys.stderr)
        elif a > b:
            j += 1
            missing += [(b, 0, uuid, r)]
        else:
            i += 1
            missing += [(a, 1, None, r)]

    for u, s in matches.viewitems():
        prefix, num = Conference.parse_sortid_string(s)
        group = conference.group_for_brief(prefix)
        sid = (group.prefix << 16) | num
        andback = conference.sort_id_to_string(sid)
        #print("[%s -> %5s] %d [%s]" % (u, s, sid, andback), file=sys.stderr)
        amap[u].sort_id = sid

    u = 1
    ugroup = conference.group_for_brief("U")
    for m in missing:
        if m[1]:
            print("> %s [missing in gca]" % (m[0]), file=sys.stderr)
        else:
            print("< %s [missing in csv]" % (m[0]), file=sys.stderr)
            uuid, s = m[2], m[0]
            sid = (ugroup.prefix << 16) | u
            amap[uuid].sort_id = sid
            andback = conference.sort_id_to_string(sid)
            u += 1
            print("  %s -> %d [%s]" % (uuid, sid, andback), file=sys.stderr)

    data = Abstract.to_json(abstracts)
    sys.stdout.write(data.encode('utf-8'))
    print("%d assigned; %d missing" % (len(matches), len(missing)), file=sys.stderr)

if __name__ == "__main__":
    main()
