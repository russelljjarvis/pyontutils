#!/usr/bin/env python3.6
"""
    A collection of reused functions and classes.
"""

import os
import re
import asyncio
import inspect
from datetime import date
from functools import wraps
from multiprocessing import Manager
import psutil
import rdflib
from rdflib.extras import infixowl

rdflib.plugin.register('nifttl', rdflib.serializer.Serializer, 'pyontutils.ttlser', 'CustomTurtleSerializer')

TODAY = date.isoformat(date.today())

def currentVMSKb():
    p = psutil.Process(os.getpid())
    return p.memory_info().vms

def memoryCheck(vms_max_kb):
    """ Lookup vms_max using getCurrentVMSKb """
    safety_factor = 1.2
    vms_max = vms_max_kb
    vms_gigs = vms_max / 1024 ** 2
    buffer = safety_factor * vms_max
    buffer_gigs = buffer / 1024 ** 2
    vm = psutil.virtual_memory()
    free_gigs = vm.available / 1024 ** 2
    if vm.available < buffer:
        raise MemoryError('Running this requires quite a bit of memory ~ {vms_gigs:.2f}, you have {free_gigs:.2f} of the {buffer_gigs:.2f} needed'.format(vms_gigs=vms_gigs, free_gigs=free_gigs, buffer_gigs=buffer_gigs))

def noneMembers(container, *args):
    for a in args:
        if a in container:
            return False
    return True

def anyMembers(container, *args):
    return not noneMembers(container, *args)

def allMembers(container, *args):
    return all(a in container for a in args)

def coln(n, iterable):
    """ Return an iterator on the nth column. """
    for rec in iterable:
        yield rec[n]

def setPS1(script__file__):
    text = 'Running ' + os.path.basename(script__file__)
    os.sys.stdout.write('\x1b]2;{}\x07'.format(text))

def refile(script__file__, path):
    return os.path.join(os.path.dirname(script__file__), path)

def async_getter(function, listOfArgs):
    async def future_loop(future_):
        loop = asyncio.get_event_loop()
        futures = []
        for args in listOfArgs:
            future = loop.run_in_executor(None, function, *args)
            futures.append(future)
        print('Futures compiled')
        responses = []
        for f in futures:
            responses.append(await f)
        future_.set_result(responses)
    future = asyncio.Future()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(future_loop(future))
    return future.result()

def mysql_conn_helper(host, db, user, port=3306):
    kwargs = {
        'host':host,
        'db':db,
        'user':user,
        'port':port,
        'password':None,  # no you may NOT pass it in
    }
    with open(os.path.expanduser('~/.mypass'), 'rt') as f:
        entries = [l.strip().split(':', 4) for l in f.readlines()]
    for e_host, e_port, e_db, e_user, e_pass in entries:
        e_port = int(e_port)
        if host == e_host:
            print('yes:', host)
            if  port == e_port:
                print('yes:', port)
                if db == e_db or e_db == '*':  # FIXME bad * expansion
                    print('yes:', db)
                    if user == e_user:
                        print('yes:', user)
                        kwargs['password'] = e_pass  # last entry wins
    e_pass = None
    if kwargs['password'] is None:
        raise ConnectionError('No password as found for {user}@{host}:{port}/{db}'.format(**kwargs))

    return kwargs

def _loadPrefixes():
    import yaml
    try:
        with open(os.path.expanduser('~/git/NIF-Ontology/scigraph/nifstd_curie_map.yaml'), 'rt') as f:
            curie_map = yaml.load(f)
    except FileNotFoundError:
        import requests
        curie_map = requests.get('https://github.com/SciCrunch/NIF-Ontology/raw/master/scigraph/nifstd_curie_map.yaml')
        curie_map = yaml.load(curie_map.text)

    # holding place for values that are not in the curie map
    extras = {
        #'':None,  # safety (now managed directly in the curies file)
        #'EHDAA2':'http://purl.obolibrary.org/obo/EHDAA2_',  # FIXME needs to go in curie map?

        'hasRole':'http://purl.obolibrary.org/obo/RO_0000087',
        'replacedBy':'http://purl.obolibrary.org/obo/IAO_0100001',
        'definition':'http://purl.obolibrary.org/obo/IAO_0000115',
        'importedFrom':'http://purl.obolibrary.org/obo/IAO_0000412',
        'PROTEGE':'http://protege.stanford.edu/plugins/owl/protege#',
        'ILXREPLACE':'http://ILXREPLACE.org/',
        'FIXME':'http://FIXME.org/',
        'ILX':'http://uri.interlex.org/base/ilx_', 
        'NIFTTL':'http://ontology.neuinfo.org/NIF/ttl/',
        'NIFSTD':'http://uri.neuinfo.org/nif/nifstd/',  # note that this is '' in real curies
        'NIFPRED':'http://uri.neuinfo.org/nif/nifstd/predicate/',  # XXX EXPERIMENTAL consider also 'Literal Identifier' or something like that
        'NIFRET':'http://ontology.neuinfo.org/NIF/Retired/NIF-Retired.owl#',
        'NLXWIKI':'http://neurolex.org/wiki/',
        'dc':'http://purl.org/dc/elements/1.1/',
        'dcterms':'http://purl.org/dc/terms/',
        'dctypes':'http://purl.org/dc/dcmitype/',  # FIXME there is no agreement on qnames
        'ilx':'http://uri.interlex.org/base/', 
        'nsu':'http://www.FIXME.org/nsupper#',
        'oboInOwl':'http://www.geneontology.org/formats/oboInOwl#',
        'owl':'http://www.w3.org/2002/07/owl#',
        'ro':'http://www.obofoundry.org/ro/ro.owl#',
        'skos':'http://www.w3.org/2004/02/skos/core#',
        'rdf':'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
        'rdfs':'http://www.w3.org/2000/01/rdf-schema#',
    }
    curie_map.update(extras)
    return curie_map

PREFIXES = _loadPrefixes()

def makePrefixes(*prefixes):
    return {k:PREFIXES[k] for k in prefixes}

class makeGraph:
    SYNONYM = 'OBOANN:synonym'  # dangerous with prefixes

    def __init__(self, name, prefixes=None, graph=None, writeloc='/tmp/'):
        self.name = name
        self.writeloc = writeloc
        self.namespaces = {}
        if prefixes:
            self.namespaces.update({p:rdflib.Namespace(ns) for p, ns in prefixes.items()})
        if graph:  # graph takes precidence
            self.namespaces.update({p:rdflib.Namespace(ns) for p, ns in graph.namespaces()})
        if graph is None and not prefixes:
            raise ValueError('No prefixes or graph specified.')

        if graph is not None:
            self.g = graph
        else:
            self.g = rdflib.Graph()  # default args issue

        for p, ns in self.namespaces.items():
            self.add_namespace(p, ns)
        self.namespaces.update({p:rdflib.Namespace(ns)
                                for p, ns in self.g.namespaces()})  # catchall for namespaces in self.g

    def add_known_namespace(self, prefix):
        self.add_namespace(prefix, PREFIXES[prefix])

    def add_namespace(self, prefix, namespace):
        self.namespaces[prefix] = rdflib.Namespace(namespace)
        self.g.bind(prefix, namespace)

    def del_namespace(self, prefix):
        try:
            self.namespaces.pop(prefix)
            self.g.store._IOMemory__namespace.pop(prefix)
        except KeyError:
            print('Namespace (%s) does not exist!' % prefix)
            pass

    @property
    def filename(self):
        return self.writeloc + self.name + '.ttl'

    @filename.setter
    def filename(self, filepath):
        dirname = os.path.dirname(filepath)
        self.writeloc = dirname + '/' if dirname else dirname  # allow local paths
        self.name = os.path.splitext(os.path.basename(filepath))[0]

    @property
    def ontid(self):
        ontids = list(self.g.subjects(rdflib.RDF.type, rdflib.OWL.Ontology))
        if len(ontids) > 1:
            raise TypeError('There is more than one ontid in this graph!'
                            ' The graph is not isomorphic to a single ontology!')
        return ontids[0]

    def write(self):
        """ Serialize self.g and write to self.filename"""
        ser = self.g.serialize(format='nifttl')
        with open(self.filename, 'wb') as f:
            f.write(ser)
            #print('yes we wrote the first version...', self.name)

    def expand(self, curie):
        prefix, suffix = curie.split(':',1)
        if prefix not in self.namespaces:
            raise KeyError('Namespace prefix does exist:', prefix)
        return self.namespaces[prefix][suffix]

    def check_thing(self, thing):
        if type(thing) == rdflib.Literal:
            return thing
        elif type(thing) != rdflib.term.URIRef and type(thing) != rdflib.term.BNode:
            try:
                return self.expand(thing)
            except (KeyError, ValueError) as e:
                if thing.startswith('http') and ' ' not in thing:  # so apparently some values start with http :/
                    return rdflib.URIRef(thing)
                else:
                    raise TypeError('Unknown format:', thing)
        else:
            return thing

    def add_ont(self, ontid, label, shortName=None, comment=None, version=None):
        self.add_trip(ontid, rdflib.RDF.type, rdflib.OWL.Ontology)
        self.add_trip(ontid, rdflib.RDFS.label, label)
        if comment:
            self.add_trip(ontid, rdflib.RDFS.comment, comment)
        if version:
            self.add_trip(ontid, rdflib.OWL.versionInfo, version)
        if shortName:
            self.add_trip(ontid, rdflib.namespace.SKOS.altLabel, shortName)

    def add_class(self, id_, subClassOf=None, synonyms=tuple(), label=None, autogen=False):
        self.add_trip(id_, rdflib.RDF.type, rdflib.OWL.Class)
        if autogen:
            label = ' '.join(re.findall(r'[A-Z][a-z]*', id_.split(':')[1]))
        if label:
            self.add_trip(id_, rdflib.RDFS.label, label)
        if subClassOf:
            self.add_trip(id_, rdflib.RDFS.subClassOf, subClassOf)

        [self.add_trip(id_, self.SYNONYM, s) for s in synonyms]

    def del_class(self, id_):
        id_ = self.check_thing(id_)
        for p, o in self.g.predicate_objects(id_):
            self.g.remove((id_, p, o))
            if type(o) == rdflib.BNode():
                self.del_class(o)

    def add_ap(self, id_, label=None, addPrefix=True):
        """ Add id_ as an owl:AnnotationProperty"""
        self.add_trip(id_, rdflib.RDF.type, rdflib.OWL.AnnotationProperty)
        if label:
            self.add_trip(id_, rdflib.RDFS.label, label)
            if addPrefix:
                prefix = ''.join([s.capitalize() for s in label.split()])
                namespace = self.expand(id_)
                self.add_namespace(prefix, namespace)

    def add_op(self, id_, label=None, subPropertyOf=None, inverse=None, transitive=False, addPrefix=True):
        """ Add id_ as an owl:ObjectProperty"""
        self.add_trip(id_, rdflib.RDF.type, rdflib.OWL.ObjectProperty)
        if inverse:
            self.add_trip(id_, rdflib.OWL.inverseOf, inverse)
        if subPropertyOf:
            self.add_trip(id_, rdflib.RDFS.subPropertyOf, subPropertyOf)
        if label:
            self.add_trip(id_, rdflib.RDFS.label, label)
            if addPrefix:
                prefix = ''.join([s.capitalize() for s in label.split()])
                namespace = self.expand(id_)
                self.add_namespace(prefix, namespace)
        if transitive:
            self.add_trip(id_, rdflib.RDF.type, rdflib.OWL.TransitiveProperty)

    def add_trip(self, target, edge, value):
        if not value:  # no empty values!
            return
        target = self.check_thing(target)
        edge = self.check_thing(edge)
        try:
            if value.startswith(':') and ' ' in value:  # not a compact repr AND starts with a : because humans are insane
                value = ' ' + value
            value = self.check_thing(value)
        except (TypeError, AttributeError) as e:
            value = rdflib.Literal(value)  # trust autoconv
        self.g.add( (target, edge, value) )

    def del_trip(self, s, p, o):
        self.g.remove(tuple(self.check_thing(_) for _ in (s, p, o)))

    def add_hierarchy(self, parent, edge, child):
        """ Helper function to simplify the addition of part_of style
            objectProperties to graphs. FIXME make a method of makeGraph?
        """
        if type(parent) != rdflib.URIRef:
            parent = self.check_thing(parent)

        if type(edge) != rdflib.URIRef:
            edge = self.check_thing(edge)

        if type(child) != infixowl.Class:
            if type(child) != rdflib.URIRef:
                child = self.check_thing(child)
            child = infixowl.Class(child, graph=self.g)

        restriction = infixowl.Restriction(edge, graph=self.g, someValuesFrom=parent)
        child.subClassOf = [restriction] + [c for c in child.subClassOf]

    def add_recursive(self, triple, source_graph):
        self.g.add(triple)
        if isinstance(triple[-1], rdflib.BNode):
            for t_ in source_graph.triples((triple[-1], None, None)):
                self.add_recursive(t_, source_graph)

    def replace_uriref(self, find, replace):  # find and replace on the parsed graph
        # XXX warning this does not update cases where an iri is in an annotation property!
        #  if you need that just use sed
        # XXX WARNING if you are doing multiple replaces you need to replace the ENTIRE
        #  set first, and THEN transfer those, otherwise you will insert half replaced
        #  triples into a graph!

        find = self.check_thing(find)

        for i in range(3):
            trip = [find if i == _ else None for _ in range(3)]
            for s, p, o in self.g.triples(trip):
                rep = [s, p, o]
                rep[i] = replace
                self.add_trip(*rep)
                self.g.remove((s, p, o))

    def replace_subject_object(self, p, s, o, rs, ro):  # useful for porting edges to equivalent classes
        self.add_trip(rs, p, ro)
        self.g.remove((s, p, o))

    def get_equiv_inter(self, curie):
        """ get equivelant classes where curie is in an intersection """
        start = self.qname(self.expand(curie))  # in case something is misaligned
        qstring = """
        SELECT DISTINCT ?match WHERE {
        ?match owl:equivalentClass/owl:intersectionOf/rdf:rest*/rdf:first %s .
        }""" % start
        return [_ for (_,) in self.g.query(qstring)]  # unpack...

    def qname(self, uri, generate=False):
        """ Given a uri return the qname if it exists, otherwise return the uri. """
        try:
            prefix, namespace, name = self.g.namespace_manager.compute_qname(uri, generate=generate)
            qname = ':'.join((prefix, name))
            return qname
        except (KeyError, ValueError) as e :
            return uri.toPython() if isinstance(uri, rdflib.URIRef) else uri

    def make_scigraph_json(self, edge, label_edge=None, direct=False):  # for checking trees
        if label_edge is None:
            label_edge = rdflib.RDFS.label
        else:
            label_edge = self.expand(label_edge)
        json_ = {'nodes':[], 'edges':[]}
        restriction = self.expand(edge)
        if direct:
            #trips = list(self.g.triples((None, restriction, None)))
            pred = restriction
            done = []
            print(repr(pred))
            #for obj, sub in self.g.subject_objects(pred):  # yes these are supposed to be flipped?
            for sub, obj in self.g.subject_objects(pred):  # or maybe they aren't?? which would explain some of my confusion
                try:
                    olab = list(self.g.objects(obj, label_edge))[0].toPython()
                except IndexError:  # no label
                    olab = obj.toPython()
                try:
                    slab = list(self.g.objects(sub, label_edge))[0].toPython()
                except IndexError:  # no label
                    slab = sub.toPython()

                obj = self.qname(obj)
                sub = self.qname(sub)
                json_['edges'].append({'sub':sub,'pred':edge,'obj':obj})
                if sub not in done:
                    node = {'lbl':slab,'id':sub, 'meta':{}}
                    #if sdep: node['meta'][rdflib.OWL.deprecated.toPython()] = True
                    json_['nodes'].append(node)
                    done.append(sub)
                if obj not in done:
                    node = {'lbl':olab,'id':obj, 'meta':{}}
                    #if odep: node['meta'][rdflib.OWL.deprecated.toPython()] = True
                    json_['nodes'].append(node)
                    done.append(obj)
            return json_

        #linkers = list(self.g.subjects(rdflib.OWL.onProperty, restriction))
        done = []
        for linker in self.g.subjects(rdflib.OWL.onProperty, restriction):
            try:
                obj = list(self.g.objects(linker, rdflib.OWL.someValuesFrom))[0]
            except IndexError:
                obj = list(self.g.objects(linker, rdflib.OWL.allValuesFrom))[0]
            if type(obj) != rdflib.term.URIRef:
                continue  # probably encountere a unionOf or something and don't want
            try:
                olab = list(self.g.objects(obj, label_edge))[0].toPython()
            except IndexError:  # no label
                olab = obj.toPython()
            odep = True if list(self.g.objects(obj, rdflib.OWL.deprecated)) else False
            obj = self.qname(obj)
            sub = list(self.g.subjects(rdflib.RDFS.subClassOf, linker))[0]
            try:
                slab = list(self.g.objects(sub, label_edge))[0].toPython()
            except IndexError:  # no label
                slab = sub.toPython()
            sdep = True if list(self.g.objects(sub, rdflib.OWL.deprecated)) else False
            try:
                sub = self.qname(sub)
            except:  # rdflib has iffy error handling here so need to catch unsplitables
                print('Could not split the following uri:', sub)

            json_['edges'].append({'sub':sub,'pred':edge,'obj':obj})
            if sub not in done:
                node = {'lbl':slab,'id':sub, 'meta':{}}
                if sdep: node['meta'][rdflib.OWL.deprecated.toPython()] = True
                json_['nodes'].append(node)
                done.append(sub)
            if obj not in done:
                node = {'lbl':olab,'id':obj, 'meta':{}}
                if odep: node['meta'][rdflib.OWL.deprecated.toPython()] = True
                json_['nodes'].append(node)
                done.append(obj)

        return json_

def createOntology(filename=    'temp-graph',
                   name=        'Temp Ontology',
                   prefixes=    None,  # is a dict
                   shortname=   None,  # 'TO'
                   comment=     None,  # 'This is a temporary ontology.'
                   version=     TODAY,
                   path=        'ttl/generated/',
                   local_base=  os.path.expanduser('~/git/NIF-Ontology/'),
                   #remote_base= 'https://raw.githubusercontent.com/SciCrunch/NIF-Ontology/master/',
                   remote_base= 'http://ontology.neuinfo.org/NIF/',
                   imports=     tuple()):
    writeloc = local_base + path
    ontid = remote_base + path + filename + '.ttl'
    if shortname is not None and prefixes is not None and 'skos' not in prefixes:
        prefixes.update(makePrefixes('skos'))
    graph = makeGraph(filename, prefixes=prefixes, writeloc=writeloc)
    graph.add_ont(ontid, name, shortname, comment, version)
    for import_ in imports:
        graph.add_trip(ontid, rdflib.OWL.imports, import_)
    return graph

def chunk_list(list_, size):
    """ Split a list list_ into sublists of length size.
        NOTE: len(chunks[-1]) <= size. """
    ll = len(list_)
    chunks = []
    for start, stop in zip(range(0, ll, size), range(size, ll, size)):
        chunks.append(list_[start:stop])
    chunks.append(list_[stop:])  # snag unaligned chunks from last stop
    return chunks

class dictParse:
    """ Base class for building dict parsers (that can also handle lists).
        Methods should be named after the keys in the dict and specify
        what to do with the contents.
    """
    def __init__(self, thing, order=[]):
        if type(thing) == dict:
            if order:
                for key in order:
                    func = getattr(self, key, None)
                    if func:
                        func(thing.pop(key))
            self._next_dict(thing)

        #elif type(thing) == list:
            #self._next_list(thing)
        else:
            print('NOPE')

    def _next_dict(self, dict_):
        for key, value in dict_.items():
            func = getattr(self, key, None)
            if func:
                func(value)

    def _next_list(self, list_):
        for value in list_:
            if type(value) == dict:
                self._next_dict(value)

    def _terminal(self, value):
        print(value)
        pass

class rowParse:
    """ Base class for parsing a list of fixed lenght lists whose
        structure is defined by a header (eg from a csv file).
        Methods should match the name of the 'column' header.
    """

    class SkipError(BaseException):
        pass

    def __init__(self, rows, header=None, order=[]):
        if header is None:
            header = [c.split('(')[0].strip().replace(' ','_').replace('+','') for c in rows[0]]
            rows = rows[1:]
        eval_order = []
        self._index_order = []
        for column in order:
            index = header.index(column)
            self._index_order.append(index)
            eval_order.append(header.pop(index))
        eval_order.extend(header)  # if not order then just do header order

        self.lookup = {index:name for index, name in enumerate(eval_order)}

        for name, obj in inspect.getmembers(self):
            if inspect.ismethod(obj) and not name.startswith('_'):  # FIXME _ is hack
                _set = '_set_' + name
                setattr(self, _set, set())
                @wraps(obj)
                def getunique(value, set_=_set, func=obj):  # ah late binding hacks
                    getattr(self, set_).add(value)
                    return func(value)
                setattr(self, name, getunique)

        self._next_rows(rows)
        self._end()

    def _order_enumerate(self, row):
        i = 0
        for index in self._index_order:
            yield i, row.pop(index)
            i += 1
        for value in row:
            yield i, value
            i += 1

    def _next_rows(self, rows):
        for self._rowind, row in enumerate(rows):
            skip = False
            for i, value in self._order_enumerate(row):
                func = getattr(self, self.lookup[i], None)
                if func:
                    try:
                        func(value)
                    except self.SkipError:
                        skip = True  # ick
                        break
            if not skip:
                self._row_post()

    def _row_post(self):
        """ Run this code after all columns have been parsed """
        pass

    def _end(self):
        """ Run this code after all rows have been parsed """
        pass

class _TermColors:
    ENDCOLOR = '\033[0m'
    colors = dict(
    BOLD = '\033[1m',
    FAINT = '\033[2m',  # doesn't work on urxvt
    IT = '\033[3m',
    UL = '\033[4m',
    BLINKS = '\033[5m',
    BLINKF = '\033[6m',  # same as S?
    REV = '\033[7m',
    HIDE = '\033[8m',  # doesn't work on urxvt
    XOUT = '\033[9m',  # doesn't work on urxvt
    FONT1 = '\033[10m',  # doesn't work on urxvt use '\033]50;%s\007' % "fontspec"
    FONT2 = '\033[11m',  # doesn't work on urxvt
    FRAKTUR = '\033[20m',  # doesn't work on urxvt
    OFF_BOLD = '\033[21m',
    NORMAL = '\033[22m',
    OFF_IT = '\033[23m',
    OFF_UL = '\033[24m',
    OFF_BLINK = '\033[25m',
    POSITIVE = '\033[27m',
    OFF_HIDE = '\033[28m',
    RED = '\033[91m',
    GREEN = '\033[92m',
    YELLOW = '\033[93m',
    BLUE = '\033[94m',
    )

    def __init__(self):
        for color, esc in self.colors.items():  # esc blocks runtime changes
            def latebindingfix(string, e=esc):
                return self.endcolor(e + string)
            setattr(self, color.lower(), latebindingfix)

    def endcolor(self, string):
        if string.endswith(self.ENDCOLOR):
            return string
        else:
            return string + self.ENDCOLOR

TermColors = _TermColors()

class scigPrint:

    _shorten_ = {
        'PR':'http://purl.obolibrary.org/obo/PR_',
        'RO':'http://purl.obolibrary.org/obo/RO_',
        'dc':'http://purl.org/dc/elements/1.1/',
        'BFO':'http://purl.obolibrary.org/obo/BFO_',
        'owl':'http://www.w3.org/2002/07/owl#',
        'rdfs':'http://www.w3.org/2000/01/rdf-schema#',
        'skos':'http://www.w3.org/2004/02/skos/core#',
        'NIFGA':'http://ontology.neuinfo.org/NIF/BiomaterialEntities/NIF-GrossAnatomy.owl#',
        'OBOANN':'http://ontology.neuinfo.org/NIF/Backend/OBO_annotation_properties.owl#',  # FIXME needs to die a swift death
        'oboInOwl':'http://www.geneontology.org/formats/oboInOwl#',
        'NIFSTD':'http://uri.neuinfo.org/nif/nifstd/',  # note that this is '' in real curies
        'NIFSUB':'http://ontology.neuinfo.org/NIF/BiomaterialEntities/NIF-Subcellular.owl#',
        'ro':'http://www.obofoundry.org/ro/ro.owl#',
        'UBERON':'http://purl.obolibrary.org/obo/UBERON_',
        'BIRNANN':'http://ontology.neuinfo.org/NIF/Backend/BIRNLex_annotation_properties.owl#',
        'NCBITaxon':'http://purl.obolibrary.org/obo/NCBITaxon_',
        'BRAINInfo':'http://braininfo.rprc.washington.edu/centraldirectory.aspx?ID=',
        'PMID':'http://www.ncbi.nlm.nih.gov/pubmed/',
    }

    shorten = {v:k for k, v in _shorten_.items()}

    @staticmethod
    def wrap(string, start, ind, wrap_=80):
        if len(string) + start <= wrap_:
            return string
        else:
            out = ''
            ends = [_ for _ in range(wrap_ - start, len(string), wrap_ - ind - 4)] + [None]
            starts = [0] + [e for e in ends]
            blocks = [string[s:e] if e else string[s:] for s, e in zip(starts, ends)]
            return ('\n' + ' ' * (ind + 4)).join(blocks)

    @staticmethod
    def sv(asdf, start, ind):
        if type(asdf) is not bool and asdf.startswith('http'):
            for iri, short in scigPrint.shorten.items():
                if iri in asdf:
                    return scigPrint.wrap(asdf.replace(iri, short + ':'), start, ind)
            print('YOU HAVE FAILED!?', asdf)
            return scigPrint.wrap(repr(asdf), start, ind)
        else:
            return scigPrint.wrap(repr(asdf), start, ind)

    @staticmethod
    def pprint_node(node):
        nodes = node['nodes']
        if not nodes:
            return  # no node... probably put a None into SciGraph
        else:
            node = nodes[0]  # no edges here...
        print('---------------------------------------------------')
        print(node['id'], '  ', node['lbl'])
        print()
        scigPrint.pprint_meta(node['meta'])
        print('---------------------------------------------------')

    @staticmethod
    def pprint_meta(meta):
        for k, v in sorted(meta.items()):
            if k in ('curie', 'iri'):
                continue
            for iri, short in scigPrint.shorten.items():
                if iri in k:
                    k = k.replace(iri, short + ':')
                    break
            if v is not None:
                base = ' ' * 4 + '%s:' % k
                if hasattr(v, '__iter__'):
                    if len(v) > 1:
                        print(base, '[')
                        _ = [print(' ' * 8 + scigPrint.sv(_, 8, 8)) for _ in v]
                        print(' ' * 4 + ']')
                    elif len(v) == 1:
                        asdf = v[0]
                        print(base, scigPrint.sv(asdf, len(base) + 1, 4))
                    else:
                        pass
                else:
                    print(base, scigPrint.sv(v, len(base) + 1, 4))

    @staticmethod
    def pprint_edge(edge):
        def fix(value):
            for iri, short in scigPrint.shorten.items():
                if iri in value:
                    return value.replace(iri, short + ':')
            return value

        e = {k:fix(v) for k, v in edge.items()}
        print('({pred} {sub} {obj}) ; {meta}'.format(**e))

    @staticmethod
    def pprint_neighbors(result):
        print('\tnodes')
        for node in sorted(result['nodes'], key = lambda n: n['id']):
            scigPrint.pprint_node({'nodes':[node]})
        print('\tedges')
        for edge in sorted(result['edges'], key = lambda e: e['pred']):
            scigPrint.pprint_edge(edge)

