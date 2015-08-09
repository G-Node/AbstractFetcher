#!/usr/bin/env python
# Quick hack to parse frontiers abstracts text
#
# Copyright (c) 2012 Christian Kellner <kellner@bio.lmu.de>.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# -*- coding: utf8 -*-
import urlparse

__author__ = 'Christian Kellner'

import codecs
import re

from lxml import etree
import argparse
import sys
import json

def Handler(key):
    def decorator(func):
        if not '::' in key:
            token = key
            state = '*'
        else:
            words = key.split('::')
            token = words[1]
            state = words[0]

        func.handler = (token, state)
        return func
    return decorator

class Converter(object):
    def __init__(self):
        self._debug = 0
        self._state = 'Event'
        self._events = []
        self._handler = {}
        self._linenum = 0
        self._re_author = re.compile(u"(\D+)((?:,? ?[0-9]\*?)+)(?:, | and )?")

        for (k, v) in self.__class__.__dict__.iteritems():
            if hasattr(v, 'handler'):
                token = v.handler[0]
                state = v.handler[1]
                self.add_handler (token, state, getattr(self, k))


    def add_handler(self, token, state, func):
        token = token.lower()
        handler = self._handler
        if not handler.has_key(token):
            handler[token] = {}

        if handler[token].has_key(state):
            raise Exception('Duplicated T-S pair')

        if self._debug:
            sys.stderr.write('Adding %10s::%-15s %s\n' % (state, token, func))

        handler[token][state] = func
        self._handler = handler

    def find_handler(self, line):
        token = line.rstrip().lower()
        token = token.rstrip('123456789') #hack for figure numbers
        if ':' in token:
            words = token.split(':')
            token = words[0]

        if not token in self._handler:
            token = '@text'

        try:
            handler = self._handler[token]
        except KeyError:
            raise Exception('%s <- no handler register for token' % token)

        state = self.state
        if not self.state in handler:
            #print 'No specific handler found for %s::%s [%s]' % (state, token, handler)
            state = '*'

        try:
            handler = handler[state]
        except KeyError:
            raise Exception('%s::%s not handled' % (token, state))
        #sys.stderr.write('%s -> %s\n' % (token, handler))
        return handler

    def split_keywords(self, line):
        split_points = ['Conference:',
                        'Presentation Type:',
                        'Topic:',
                        'Citation:',
                        'Conference Abstract:',
                        'doi:',
                        'Received:',
                        'Published Online:',
                        '* Correspondence:']

        lines = []
        for sp in reversed(split_points):
            idx = line.rfind(sp)
            if idx == -1:
                continue
            lines.append(line[idx:].strip())
            line = line[:idx]
        lines.append(line.strip())
        #sys.stderr.write(str(lines))
        return reversed(lines)

    def preprocess(self, line):
        if line.startswith('Keywords'):
            return self.split_keywords(line)
        new_line = line.replace('EVENT ABSTRACT Back to Event', 'EVENT ABSTRACT')
        return [ new_line ]

    def convert(self, input):
        event = None
        for line in input:
            self._linenum += 1

            try:
                lines = self.preprocess(line)
                for l in lines:
                    handler = self.find_handler(l)
                    event = handler(event, l.rstrip())
            except :
                sys.stderr.write('LINE: %d\n' % self._linenum)
                raise
        if event:
            self._events.append(event)

    # Handler
    @Handler('http')
    def handle_http(self, event, line):
        self._http = line
        self.state = 'Event'
        return event

    @Handler('Event Abstract')
    def handle_event(self, event, line):

        if event and len(event):
            self._events.append(event)

        event = {}
        if self._http:
            event['url'] = self._http
            url = urlparse.urlparse (self._http)
            ids = urlparse.parse_qs(url[4])
            #event['frontid'] = ids['articleid'][0]
            #event['frontsubid'] = ids['submissionid'][0]
            #FIXME remeber doi!
            self._http = None
        self.state = 'Title'
        return event

    @Handler('Title::@Text')
    def handle_title(self, event, line):
        self.event_add_text(event, 'title', line)
        #event['title'] = line
        self.state = 'Authors'
        return event

    @Handler('Authors::@Text')
    def handle_authors(self, event, line):

        #catch one pathologcial abstract with a newline in the title
        if line == '':
            sys.stderr.write('%5d: Empty authors line, assuming title!\n' % self._linenum)
            self.state = 'Title'
            event['title'] += line
            return event

        l = self._re_author.findall(line)

        if not len(l):
            sys.stderr.write('%5d: No authors found, assuming title!\n' % self._linenum)
            event['title'] += line
            return event

        authors = []
        n_affiliations = 0
        for match in l:
            author = {'name' : match[0]}
            af = re.findall('(?:([0-9]+)(\*?),?)', match[1])
            author['affiliations'] = [int(x[0]) for x in af]

            if '*' in match[1]:
                author['corresponding'] = True
            authors.append(author)
            n_affiliations = max(n_affiliations, max(author['affiliations']))



        event['authors'] = authors
        event['affiliations'] = {x : None for x in xrange(1, n_affiliations+1)}

        self._cur_affiliation = 1
        self._n_affiliations = n_affiliations
        self.state = 'Affiliation'
        return event

    @Handler('Affiliation::@Text')
    def handle_affiliation(self, event, line):
        #sys.stderr.write(' [%s]\n' % line)
        if line == '\n' or line == '':
            return event
        af = line
        for d in '\t1234567890':
            af = af.replace(d, '')
        af = af.lstrip()
        event['affiliations'][self._cur_affiliation] = af
        self._cur_affiliation += 1
        if self._cur_affiliation > self._n_affiliations:
            self.state = 'Abstract'
        return event

    @Handler('Abstract::@Text')
    def handle_abstract(self, event, line):
        event = self.event_add_text(event, 'abstract', line)
        return event

    @Handler('Abstract::Figure ')
    def handle_figure(self, event, line):
        if len(line) > len('Figure X'):
            sys.stderr.write("F: %s\n" % line)
            event = self.event_add_text(event, 'abstract', line)
            return event

        if not event.has_key('nfigures'):
            event['nfigures'] = 0

        curFig = int (line[7:])
        event['nfigures'] = max(event['nfigures'], curFig)
        return event

    @Handler('*::Acknowledgements')
    def begin_acknowledgements(self, event, line):
        self.state = 'Acknowledgements'
        return event

    @Handler('Acknowledgements::@Text')
    def handle_acknowledgements(self, event, line):
        event = self.event_add_text(event, 'acknowledgements', line)
        return event

    @Handler('*::Conflict of Interest')
    def begin_coi(self, event, line):
        self.state = 'CoI'
        return event

    @Handler('CoI::@Text')
    def handle_coi(self, event, line):
        self.event_add_text(event, 'coi', line)
        return event

    @Handler('*::References')
    def begin_refs(self, event, line):
        self.state = 'Refs'
        return event

    @Handler('Refs::@Text')
    def handle_refs(self, event, line):
        self.event_add_text(event, 'refs', line)
        return event

    @Handler('*::Keywords')
    def handle_keywords(self, event, line):
        event['keywords'] = [x.strip() for x in line[9:].split(',')]
        self.state = 'Event'
        return event

    @Handler('*::Presentation Type')
    def handle_type(self, event, line):
        event['type'] = line[18:].strip()
        return event

    @Handler('*::Topic')
    def handle_topic(self, event, line):
        event['topic'] = line[7:]
        return event

    @Handler('*::Citation')
    def handle_citation(self, event, line):
        event['cite'] = line[9:]
        self.state = 'Cite'
        return event

    @Handler('Cite::@Text')
    def handle_citation_more(self, event, line):
        event['cite'] += line
        self.state = 'Cite'
        return event

    @Handler('*::* Correspondence')
    def handle_correspondence(self, event, line):
        event['correspondence'] = line[17:]
        self.state = 'Cor'
        return event

    @Handler('Cor::@Text')
    def handle_corr_more(self, event, line):
        event['correspondence'] += '\n' + line
        return event

    @Handler('*::Conference')
    def handle_conference(self, event, line):
        return event

    @Handler('*::Published Online')
    def handle_published(self, event, line):
        return event

    @Handler('*::Received')
    def handle_received(self, event, line):
        return event
    
    @Handler('*::doi')
    def handle_doi(self, event, line):
        event['doi'] = line
        return event

    @Handler('< Back')
    def handle_eoa(self, event, line):
        if event:
            self._events.append(event)
        event = {}
        self.state = 'Event'
        return event

    @Handler('Event::@Text')
    def handle_root_text(self, event, line):
        if not line == '':
            sys.stderr.write('%5d: [W] URT: %s\n' % (self._linenum, line))
        #ignore
        return event

    @property
    def events(self):
        return self._events

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        self._state = value

    @classmethod
    def event_add_text(cls, event, key, text, add_newline=True):
        if key not in event:
            if text == '':
                return event
            else:
                event[key] = ''

        if add_newline:
            text += '\n'
        event[key] += text
        #sys.stderr.write('{%s}\n' % text)
        return event


class JSONWriter(object):
    def __init__(self, abstracts, event='BC12'):
        self._abstracts = abstracts
        self._event = event

    def write(self):
        return json.dumps(self._abstracts, indent=4)


class XmlWriter(object):
    def __init__(self, abstracts, event='BC12'):
        self._abstracts = abstracts
        self._event = event

    def write_abstract(self, node, abstract):
        #sys.stderr.write('%s\n' % abstract)
        title = etree.SubElement(node, 'title')
        title.text = abstract['title']
        for author in abstract['authors']:
            author_node = etree.SubElement(node, 'author')
            author_node.text = author['name']

        text = etree.SubElement(node, 'text')
        txt = abstract['abstract']
        text.text = txt

        if 'acknowledgements' in abstract:
            ack = etree.SubElement(node, 'acknowledgements')
            ack.text = abstract['acknowledgements']

        af_root = etree.SubElement(node, 'affiliations')
        for k,af in abstract['affiliations'].items():
            af_node = etree.SubElement(af_root, 'affiliation', index=str(k))
            af_node.text = af

        topic = etree.SubElement(node, 'topic')
        topic.text = abstract['topic']

        keywords = etree.SubElement(node, 'keywords')
        for keyword in abstract['keywords']:
            kw_node = etree.SubElement(keywords, 'keyword')
            kw_node.text = keyword


    def write(self):
        root = etree.Element(self._event)
        for i,abstract in enumerate (self._abstracts):
            node = etree.SubElement(root, 'abstract', type=abstract['type'])
            self.write_abstract(node, abstract)

        str = etree.tostring(root, pretty_print=True, encoding='utf8')
        return str

def main():
    parser = argparse.ArgumentParser(description='Convert frontiers abstracts files')
    parser.add_argument('input', type=str, default=sys.stdin)

    args = parser.parse_args()
    f = codecs.open(args.input, encoding='utf8')
    C = Converter()
    C.convert(f)
    events = C.events

    writer = JSONWriter(events)
    print(writer.write())
    sys.stderr.write("# of abstracts: %d\n" % len(events))

    #for e in events:
    #    print e

    #xmlwriter = XmlWriter(events)
    #print xmlwriter.write()


if __name__ == '__main__':
    main()
