"""
    sphinxcontrib.openapi
    ---------------------

    The OpenAPI spec renderer for Sphinx. It's a new way to document your
    RESTful API. Based on ``sphinxcontrib-httpdomain``.

    :copyright: (c) 2016, Ihor Kalnytskyi.
    :license: BSD, see LICENSE for details.
"""

from __future__ import unicode_literals

import io
import itertools
import collections

import yaml
import jsonschema

from docutils import nodes
from docutils.parsers.rst import Directive, directives
from docutils.statemachine import ViewList

from sphinx.util.nodes import nested_parse_with_titles

def _resolve_refs(uri, spec):
    """Resolve JSON references in a given dictionary.

    OpenAPI spec may contain JSON references to its nodes or external
    sources, so any attempt to rely that there's some expected attribute
    in the spec may fail. So we need to resolve JSON references before
    we use it (i.e. replace with referenced object). For details see:

        https://tools.ietf.org/html/draft-pbryan-zyp-json-ref-02

    The input spec is modified in-place despite being returned from
    the function.
    """
    resolver = jsonschema.RefResolver(uri, spec)

    def _do_resolve(node):
        if isinstance(node, collections.Mapping) and '$ref' in node:
            with resolver.resolving(node['$ref']) as resolved:
                return resolved
        elif isinstance(node, collections.Mapping):
            for k, v in node.items():
                node[k] = _do_resolve(v)
        elif isinstance(node, (list, tuple)):
            for i in range(len(node)):
                node[i] = _do_resolve(node[i])
        return node

    return _do_resolve(spec)


def _httpresource(endpoint, method, properties):
    parameters = properties.get('parameters', [])
    responses = properties['responses']
    indent = '   '

    yield '.. http:{0}:: {1}'.format(method, endpoint)
    yield '   :synopsis: {0}'.format(properties.get('summary', 'null'))
    yield ''

    if 'summary' in properties:
        for line in properties['summary'].splitlines():
            yield '{indent}**{line}**'.format(**locals())
        yield ''

    if 'description' in properties:
        for line in properties['description'].splitlines():
            yield '{indent}{line}'.format(**locals())
        yield ''

    # print request's route params
    for param in filter(lambda p: p['in'] == 'path', parameters):
        yield indent + ':param {type} {name}:'.format(**param)
        for line in param.get('description', '').splitlines():
            yield '{indent}{indent}{line}'.format(**locals())

    # print request's query params
    for param in filter(lambda p: p['in'] == 'query', parameters):
        yield indent + ':query {type} {name}:'.format(**param)
        for line in param.get('description', '').splitlines():
            yield '{indent}{indent}{line}'.format(**locals())

    # print response status codes in sorted order
    for status in sorted(responses.keys()):
        response = responses[status]
        yield '{indent}:status {status}:'.format(**locals())
        for line in response['description'].splitlines():
            yield '{indent}{indent}{line}'.format(**locals())
        if 'schema' in response:
            schema = response['schema']
            desc = ''
            if 'title' in schema:
                desc = ':json:object:`{0}` object'.format(schema['title'])
            if 'type' in schema:
                desc = schema['type']
                if schema['type'] == 'array' and 'items' in schema:
                    if 'type' in schema['items']:
                        desc = schema['items']['type']
                    if 'title' in schema['items']:
                        desc = 'array of :json:object:`{0}` objects'.format(schema['items']['title'])
            yield '{indent}{indent}Returns: {desc}'.format(**locals())

    # print request header params
    for param in filter(lambda p: p['in'] == 'header', parameters):
        yield indent + ':reqheader {name}:'.format(**param)
        for line in param.get('description', '').splitlines():
            yield '{indent}{indent}{line}'.format(**locals())

    # print response headers
    for status, response in responses.items():
        for headername, header in response.get('headers', {}).items():
            yield indent + ':resheader {name}:'.format(name=headername)
            for line in header['description'].splitlines():
                yield '{indent}{indent}{line}'.format(**locals())

    yield ''


def _jsonresource(definition, data):
    indent = '   '

    yield '.. json:object:: {0}'.format(definition)
    yield ''

    if 'description' in data:
        yield '{indent}{desc}'.format(indent=indent, desc=data['description'])
        yield ''

    if 'properties' in data:
        for field in data['properties']:
            desc = ''
            if 'description' in data['properties'][field]:
                desc = data['properties'][field]['description']
            data_type = ''
            if 'type' in data['properties'][field]:
                data_type = data['properties'][field]['type']
            if data_type == 'array' and 'items' in data['properties'][field]:
                data_type = '[]'
                if 'type' in data['properties'][field]['items']:
                    data_type = '[{0}]'.format(data['properties'][field]['items']['type'])
                if 'title' in data['properties'][field]['items']:
                    data_type = ''
                    json_obj = ':json:object:`{0}`'.format(data['properties'][field]['items']['title'])
                    yield '{indent}:proptype {field}: [{json_obj}]'.format(**locals())
            yield '{indent}:property {data_type} {field}: {desc}'.format(**locals())


def _normalize_spec(spec, **options):
    # OpenAPI spec may contain JSON references, so we need resolve them
    # before we access the actual values trying to build an httpdomain
    # markup. Since JSON references may be relative, it's crucial to
    # pass a document URI in order to properly resolve them.
    spec = _resolve_refs(options.get('uri', ''), spec)

    # OpenAPI spec may contain common endpoint's parameters top-level.
    # In order to do not place if-s around the code to handle special
    # cases, let's normalize the spec and push common parameters inside
    # endpoints definitions.
    for endpoint in spec['paths'].values():
        parameters = endpoint.pop('parameters', [])
        for method in endpoint.values():
            method.setdefault('parameters', [])
            method['parameters'].extend(parameters)


def openapi2httpdomain(spec, **options):
    generators = []

    # OpenAPI spec may contain JSON references, common properties, etc.
    # Trying to render the spec "As Is" will require to put multiple
    # if-s around the code. In order to simplify flow, let's make the
    # spec to have only one (expected) schema, i.e. normalize it.
    _normalize_spec(spec, **options)

    # If 'paths' are passed we've got to ensure they exist within an OpenAPI
    # spec; otherwise raise error and ask user to fix that.
    if 'paths' in options:
        if not set(options['paths']).issubset(spec['paths']):
            raise ValueError(
                'One or more paths are not defined in the spec: %s.' % (
                    ', '.join(set(options['paths']) - set(spec['paths'])),
                )
            )

    for endpoint in options.get('paths', spec['paths']):
        for method, properties in spec['paths'][endpoint].items():
            generators.append(_httpresource(endpoint, method, properties))

    return iter(itertools.chain(*generators))


def openapi2jsondomain(spec, **options):
    generators = []

    # OpenAPI spec may contain JSON references, common properties, etc.
    # Trying to render the spec "As Is" will require to put multiple
    # if-s around the code. In order to simplify flow, let's make the
    # spec to have only one (expected) schema, i.e. normalize it.
    _normalize_spec(spec, **options)

    # If 'definitions' are passed we've got to ensure they exist within an OpenAPI
    # spec; otherwise raise error and ask user to fix that.
    if 'definitions' in options:
        if not set(options['definitions']).issubset(spec['definitions']):
            raise ValueError(
                'One or more definitions are not defined in the spec: %s.' % (
                    ', '.join(set(options['definitions']) - set(spec['definitions'])),
                )
            )

    for definition in options.get('definitions', spec['definitions']):
        if 'properties' in spec['definitions'][definition]:
            generators.append(_jsonresource(definition, spec['definitions'][definition]))

    return iter(itertools.chain(*generators))


class OpenApi(Directive):

    required_arguments = 1                  # path to openapi spec
    final_argument_whitespace = True        # path may contain whitespaces
    option_spec = {
        'encoding': directives.encoding,    # useful for non-ascii cases :)
        'paths': lambda s: s.split(),       # endpoints to be rendered
        'definitions': lambda s: s.split()  # definitions to be rendered
    }

    def run(self):
        env = self.state.document.settings.env
        relpath, abspath = env.relfn2path(directives.path(self.arguments[0]))

        # Add OpenAPI spec as a dependency to the current document. That means
        # the document will be rebuilt if the spec is changed.
        env.note_dependency(relpath)

        # Read the spec using encoding passed to the directive or fallback to
        # the one specified in Sphinx's config.
        encoding = self.options.get('encoding', env.config.source_encoding)
        with io.open(abspath, 'rt', encoding=encoding) as stream:
            spec = yaml.safe_load(stream)

        # URI parameter is crucial for resolving relative references. So
        # we need to set this option properly as it's used later down the
        # stack.
        self.options.setdefault('uri', 'file://%s' % abspath)

        # Ensure that we do not print _all_ urls when only 'definitions' are
        # requested (and vice versa)
        if self.options.get('paths') is None and self.options.get('definitions'):
            self.options['paths'] = []

        if self.options.get('definitions') is None and self.options.get('paths'):
            self.options['definitions'] = []

        # reStructuredText DOM manipulation is pretty tricky task. It requires
        # passing dozen arguments which is not easy without well-documented
        # internals. So the idea here is to represent OpenAPI spec as
        # reStructuredText in-memory text and parse it in order to produce a
        # real DOM.
        viewlist = ViewList()
        for line in openapi2httpdomain(spec, **self.options):
            viewlist.append(line, '<openapi>')

        for line in openapi2jsondomain(spec, **self.options):
            viewlist.append(line, '<openapi>')

        # Parse reStructuredText contained in `viewlist` and return produced
        # DOM nodes.
        node = nodes.section()
        node.document = self.state.document
        nested_parse_with_titles(self.state, viewlist, node)
        return node.children


def setup(app):
    app.setup_extension('sphinxcontrib.httpdomain')
    app.setup_extension('sphinxjsondomain')
    app.add_directive('openapi', OpenApi)
