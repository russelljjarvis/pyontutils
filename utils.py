"""
    A collection of reused functions and classes.
"""

import os

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

class makeGraph:
    def __init__(self, name, prefixes):
        self.name = name
        self.namespaces = {p:rdflib.Namespace(ns) for p, ns in prefixes.items()}
        self.g = rdflib.Graph()
        [self.g.namespace_manager.bind(p, ns) for p, ns in prefixes.items()]

    def write(self):
        write_loc = '/tmp/ttl_files'
        with open('/tmp/' + self.name + '.ttl', 'wb') as f:
            f.write(self.g.serialize(format='turtle'))
        with open(write_loc, 'wt') as f:
            f.write('/tmp/' + self.name + '.ttl\n')
        os.system('java -cp ' +
            os.path.expanduser('~/git/ttl-convert/target/'
                               'ttl-convert-1.0-SNAPSHOT-jar-with-dependencies.jar') +
                  ' scicrunch.App ' + write_loc)

    def expand(self, curie):
        #print(curie)
        prefix, suffix = curie.split(':')
        if prefix not in self.namespaces:
            raise KeyError('Namespace prefix does exist:', prefix)
        return self.namespaces[prefix][suffix]

    def check_thing(self, thing):
        if type(thing) != rdflib.term.URIRef:
            try:
                return self.expand(thing)
            except (KeyError, ValueError) as e:
                if thing.startswith('http') and ' ' not in thing:  # so apparently some values start with http :/
                    return rdflib.URIRef(thing)
                else:
                    raise TypeError('Unknown format:', thing)
        else:
            return thing

    def add_node(self, target, edge, value):
        target = self.check_thing(target)
        edge = self.check_thing(edge)
        try:
            if value.startswith(':') and ' ' in value:  # not a compact repr AND starts with a : because humans are insane
                value = ' ' + value
            value = self.check_thing(value)
        except (TypeError, AttributeError) as e:
            value = rdflib.Literal(value)  # trust autoconv
        self.g.add( (target, edge, value) )

def add_hierarchy(graph, parent, edge, child):
    """ Helper function to simplify the addition of part_of style
        objectProperties to graphs. FIXME make a method of makeGraph?
    """
    restriction = infixowl.Restriction(edge, graph=graph, someValuesFrom=parent)
    child.subClassOf = [restriction] + [c for c in child.subClassOf]

def chunk_list(list_, size):
    """ Split a list list_ into sublists of length size.
        NOTE: len(chunks[-1]) <= size. """
    ll = len(list_)
    chunks = []
    for start, stop in zip(range(0, ll, size), range(size, ll, size)):
        chunks.append(list_[start:stop])
    chunks.append(list_[stop:])  # snag unaligned chunks from last stop
    return chunks
