#!/usr/bin/env python
from __future__ import print_function

import argparse
import sys
import codecs
import json
from nameparser import HumanName
import gca.core as gca
from urlparse import urlparse

def url_to_altId(u):
    o = urlparse(u)
    print(o.query)

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
    return af

def convert_author(old):
    data = old['name']
    h_name = HumanName(data)
    author = gca.Author()
    author.first_name = h_name.first
    author.middle_name = h_name.middle
    author.last_name = h_name.last
    author.affiliations = [int(x) for x in old['affiliations'] if x != '*']
    # todo: corr?
    return author

def convert_references(old):
    refs = []
    for r in old.split('\n'):
        if not r:
            continue
        ref = gca.Reference()
        ref.text = r
        refs.append(ref)
    return refs

def convert_abstract(old):
    print(old, file=sys.stderr)
    abstract = gca.Abstract()
    convert_field(old, 'title', abstract)
    convert_field(old, 'abstract', abstract, 'text')
    convert_field(old, 'acknowledgements', abstract, 'acknowledgements')
    convert_field(old, 'topic', abstract)
    convert_field(old, 'doi', abstract)

    abstract.authors = [convert_author(a) for a in old['authors']]
    abstract.affiliations = [convert_affiliation(k, v) for k, v in old['affiliations'].iteritems()]
    if 'refs' in old:
        abstract.references = convert_references(old['refs'])

    return abstract


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='old js to GCA schema js converter')
    parser.add_argument('--sort', type=str, default=None)
    parser.add_argument('file', type=str, default='-')
    args = parser.parse_args()

    fd = codecs.open(args.file, 'r', encoding='utf-8') if args.file != '-' else sys.stdin

    raw_data = fd.read()
    fd.close()
    old_js = json.loads(raw_data)
    new_objs = [convert_abstract(abs_dict) for abs_dict in old_js]

    if args.sort is not None:
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
                print('Could not find' + t)
        #sys.exit(0)

    js = gca.Abstract.to_json(new_objs)
    sys.stdout.write(js.encode('utf-8'))