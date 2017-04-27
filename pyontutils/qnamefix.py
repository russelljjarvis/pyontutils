#!/usr/bin/env python3
"""
    This file should be run in NIF-Ontology/ttl
    Run at NIF-Ontology 0f1f95c25cc46b8953f115705031919485cfc42f
"""

import os
from glob import glob
import rdflib
from pyontutils.utils import makePrefixes, PREFIXES, makeGraph
from IPython import embed

def main():
    PREFIXES.pop('OIO')  # prefer oboInOwl
    ps = {'NIFFIXME':'http://ontology.neuinfo.org/NIF/#',
          'PROTEGE':'http://protege.stanford.edu/plugins/owl/protege#',
          'DCFIXME':'http://purl.org/dc/terms/', }
    PREFIXES.update(ps)
    pi = {v:k for k, v in PREFIXES.items()}
    pi.pop(None)
    missing = []
    for f in glob('*/*.ttl') + glob('*.ttl'):
        graph = rdflib.Graph()
        graph.parse(f, format='turtle')
        namespaces = [str(n) for p, n in graph.namespaces()]
        prefs = []
        asdf = {v:k for k, v in ps.items()}
        asdf.update(pi)
        for rn, rp in asdf.items():
            for uri in list(graph.subjects()) + list(graph.predicates()) + list(graph.objects()):
                if type(uri) == rdflib.BNode:
                    continue
                if uri.startswith(rn):
                    if rp == 'OBO' or rp == 'IAO' or rp == 'NIFTTL':
                        if rp == 'IAO' and 'IAO_0000412' in uri:
                            pass
                        else:
                            continue
                    prefs.append(rp)
                    break

        if prefs:
            ps = makePrefixes(*prefs)
        else:
            ps = makePrefixes('rdfs')
        ng = makeGraph(os.path.splitext(f)[0], prefixes=ps, writeloc=os.path.expanduser('~/git/NIF-Ontology/ttl/'))
        [ng.add_node(*n) for n in graph.triples([None]*3)]
        ng.write()

if __name__ == '__main__':
    main()
