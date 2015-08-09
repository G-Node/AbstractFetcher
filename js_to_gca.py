#!/usr/bin/env python
from __future__ import print_function

import argparse
import sys
import codecs
import json
from nameparser import HumanName
import gca.core as gca
from urlparse import urlparse
import uuid


def fill_uuid(entity, old):
    if 'uuid' in old:
        id = old['uuid']
    else:
        id = uuid.uuid4()
    entity.uuid = id
    return entity


def convert_field(obj, old_name, abstract, new_name=None, def_value=None):
    if new_name is None:
        new_name = old_name
    if old_name in obj and obj[old_name]:
        data = obj[old_name]
        if type(data) == unicode or type(data) == str:
            data = data.strip()
        setattr(abstract, new_name, data)
    elif def_value is not None:
        setattr(abstract, new_name, def_value)


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

def convert_author(old):
    data = old['name']
    h_name = HumanName(data)
    author = gca.Author()
    author.first_name = h_name.first
    author.middle_name = h_name.middle
    author.last_name = h_name.last
    author.affiliations = [int(x)-1 for x in old['affiliations'] if x != '*']
    # todo: corr?
    fill_uuid(author, old)
    return author

def convert_references(old):
    refs = []
    lines = old.split('\n')
    lines = filter(lambda x: len(x) > 0, lines)

    def mk_ref(text):
        ref = gca.Reference()
        ref.text = text
        refs.append(ref)
        fill_uuid(ref, {})
        return ref

    return [mk_ref(l) for l in lines]

def convert_abstract(old, conference):
    abstract = gca.Abstract(conference=conference)
    convert_field(old, 'title', abstract)
    convert_field(old, 'abstract', abstract, 'text')
    convert_field(old, 'acknowledgements', abstract, 'acknowledgements')
    convert_field(old, 'topic', abstract)
    convert_field(old, 'doi', abstract)

    abstract.authors = [convert_author(a) for a in old['authors']]
    abstract.affiliations = [convert_affiliation(k, v) for k, v in old['affiliations'].iteritems()]
    if 'refs' in old:
        abstract.references = convert_references(old['refs'])

    fill_uuid(abstract, old)
    return abstract


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='old js to GCA schema js converter')
    parser.add_argument('--sort', type=str, default=None)
    parser.add_argument('--conference', type=str, default=None)
    parser.add_argument('file', type=str, default='-')
    args = parser.parse_args()

    conference = None
    if args.conference is not None:
        with open(args.conference) as fd:
            conference = gca.Conference.from_data(fd.read())

    fd = codecs.open(args.file, 'r', encoding='utf-8') if args.file != '-' else sys.stdin

    raw_data = fd.read()
    fd.close()
    old_js = json.loads(raw_data)
    new_objs = [convert_abstract(abs_dict, conference) for abs_dict in old_js]

    if args.sort is not None:
        if conference is None:
            raise ValueError('Need conference for prefixes')
        import pandas as pd
        df = pd.read_excel(args.sort)
        gp = df.groupby(['Abstract number', 'Article_Title'])

        for k, v in gp.groups.iteritems():
            t = k[1].strip()
            if t.startswith('"'):
                t = t[1:]
            if t.endswith('"'):
                t = t[:-1]
            found = None
            for a in new_objs:
                if a.title == t.strip():
                    found = a
                    break
            if a is None:
                print('Could not find' + t, file=sys.stderr)
                continue
            sid = k[0]
            a.poster_id = sid

    js = gca.Abstract.to_json(new_objs)
    sys.stdout.write(js.encode('utf-8'))