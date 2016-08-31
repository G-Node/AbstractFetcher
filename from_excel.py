#!/usr/bin/env python
from __future__ import print_function

import argparse
import uuid

from xlrd import open_workbook
import sys
import gca.core as gca
from nameparser import HumanName
from difflib import SequenceMatcher
import codecs


def fill_uuid(entity, old):
    if 'uuid' in old:
        id = old['uuid']
    else:
        id = uuid.uuid4()
    entity.uuid = id
    return entity


def convert_affiliation(idx, old):
    c = list(reversed(old.split(',')))
    k = len(c)
    af = gca.Affiliation()
    if k > 3:
        af.department = ", ".join(c[3:])

    if k > 2:
        af.section = c[2].strip()

    if k > 1:
        af.address = c[1].strip()

    af.country = c[0].strip()
    fill_uuid(af, old)
    return af


def convert_references(data):
    refs = []
    data = data.strip("\" ")
    if "<br />" in data:
        lines = data.split("<br />")
    else:
        lines = data.split('\n')
    lines = filter(lambda x: len(x) > 0, map(lambda x: x.strip(), lines))

    def mk_ref(text):
        ref = gca.Reference()
        ref.text = text
        refs.append(ref)
        fill_uuid(ref, {})
        return ref

    return [mk_ref(l) for l in lines]

def make_sortid(row, conference):
    idstr = row[0].value
    prefix, num = gca.Conference.parse_sortid_string(idstr)
    group = conference.group_for_brief(prefix)
    return group.prefix << 16 | num


def make_abstract(row, conference):
    abstract = gca.Abstract(conference=conference)
    abstract.title = row[1].value.strip(" \"")
    abstract.topic = row[6].value
    abstract.text = row[7].value.strip(" \"")
    abstract.references = convert_references(row[8].value)
    abstract.acknowledgements = row[9].value
    abstract.sort_id = make_sortid(row, conference)
    abstract.uuid = uuid.uuid4()
    return abstract


def make_aff(row):
    org = row[3].value
    dep = row[4].value
    af = gca.Affiliation()
    af.department = dep
    af.address = org
    af.uuid = uuid.uuid4()
    return af


def make_author(row):
    author = gca.Author()
    h_name = HumanName(row[2].value)
    author.first_name = h_name.first
    author.middle_name = h_name.middle
    author.last_name = h_name.last
    author.uuid = uuid.uuid4()
    return author


def find_abstract(abstracts, title):
    for abstract in abstracts:
        a, b = abstract.title, title
        s = SequenceMatcher(lambda x: x == " ", a, b)
        r = round(s.ratio(), 3)
        if r > 0.9:
            return abstract
    return None


def main():
    parser = argparse.ArgumentParser(description='execl to GCA')
    parser.add_argument('excel', type=str, default='-')
    parser.add_argument('data')
    parser.add_argument('conference', type=str, default=None)
    args = parser.parse_args()

    wb = open_workbook(args.excel)
    sh = wb.sheet_by_index(0)

    conference = None
    with open(args.conference) as fd:
        conference = gca.Conference.from_data(fd.read())

    fn = args.data
    fd = codecs.open(fn, 'r', encoding='utf-8') if fn != '-' else sys.stdin

    data = gca.Abstract.from_data(fd.read())

    abstracts = []

    is_first = True
    old_id = None
    old_author = None
    old_affiliation = None
    affiliations = {}
    abstract = None
    ignore = True

    for rx in range(sh.nrows):
        if is_first:
            is_first = False
            continue
        row = sh.row(rx)
        pid = row[0].value
        title = row[1].value.strip("\" ")
        author = row[2].value
        aff = row[3].value + row[4].value

        if old_id != pid:
            old_id = pid
            old_author = None
            affiliations = {}
            abstract = find_abstract(data, title)
            ignore = abstract is not None
            if not ignore:
                abstract = make_abstract(row, conference)
                print((u"new abstract: %s" % title).encode('utf-8'), file=sys.stderr)
            else:
                abstract.sort_id = make_sortid(row, conference)
            abstracts += [abstract]

        if ignore:
            continue

        if old_author != author:
            old_author = author
            au = make_author(row)
            abstract.authors += [au]
            old_affiliation = None

        if old_affiliation != aff:
            old_affiliation = aff
            au = abstract.authors[-1]
            if aff not in affiliations:
                af = make_aff(row)
                afid = len(abstract.affiliations)
                abstract.affiliations += [af]
                affiliations[aff] = afid
            else:
                afid = affiliations[aff]
            au.affiliations += [afid]

    abstracts = filter(lambda x: x is not None, abstracts)
    js = gca.Abstract.to_json(abstracts)
    sys.stdout.write(js.encode('utf-8'))

if __name__ == '__main__':
    main()
