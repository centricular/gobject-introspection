# -*- Mode: Python -*-
# GObject-Introspection - a framework for introspecting GObject libraries
# Copyright (C) 2010  Red Hat, Inc.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.
#

from __future__ import with_statement

from contextlib import contextmanager

from . import ast


class CCodeGenerator(object):
    def __init__(self, namespace,
                 out_h_filename,
                 out_c_filename,
                 function_decoration=[],
                 include_first_header=[],
                 include_last_header=[],
                 include_first_src=[],
                 include_last_src=[]):
        self.out_h_filename = out_h_filename
        self.out_c_filename = out_c_filename
        self.function_decoration = function_decoration
        self.include_first_header = include_first_header
        self.include_last_header = include_last_header
        self.include_first_src = include_first_src
        self.include_last_src = include_last_src
        self._function_bodies = {}
        self.namespace = namespace

    def gen_symbol(self, name):
        name = name.replace(' ', '_')
        return '%s_%s' % (self.namespace.symbol_prefixes[0], name)

    def _typecontainer_to_ctype(self, param):
        if (isinstance(param, ast.Parameter)
        and param.direction in (ast.PARAM_DIRECTION_OUT, ast.PARAM_DIRECTION_INOUT)):
            suffix = '*'
        else:
            suffix = ''

        if (param.type.is_equiv((ast.TYPE_STRING, ast.TYPE_FILENAME))
        and param.transfer == ast.PARAM_TRANSFER_NONE):
            return "const gchar*" + suffix

        return param.type.ctype + suffix

    def _write_prelude(self, out, func):
        if self.function_decoration:
            out.write("""
%s""" % " ".join(self.function_decoration))

        out.write("""
%s
%s (""" % (self._typecontainer_to_ctype(func.retval), func.symbol))
        l = len(func.parameters)
        if func.parameters:
            for i, param in enumerate(func.parameters):
                ctype = self._typecontainer_to_ctype(param)
                out.write('%s %s' % (ctype, param.argname))
                if i < l - 1:
                    out.write(", ")
        else:
            out.write('void')
        out.write(")")

    def _write_prototype(self, func):
        self._write_prelude(self.out_h, func)
        self.out_h.write(";\n\n")

    def _write_annotation_transfer(self, node):
        if (node.type not in ast.BASIC_TYPES or
                node.type.ctype.endswith('*')):
            self.out_c.write(" (transfer %s)" % (node.transfer, ))

    def _write_docs(self, func):
        self.out_c.write("/**\n * %s:\n" % (func.symbol, ))
        for param in func.parameters:
            self.out_c.write(" * @%s" % (param.argname, ))
            if param.direction in (ast.PARAM_DIRECTION_OUT,
                                   ast.PARAM_DIRECTION_INOUT):
                if param.caller_allocates:
                    allocate_string = ' caller-allocates'
                else:
                    allocate_string = ''
                self.out_c.write(": (%s%s) " % (param.direction,
                                                allocate_string))
                self._write_annotation_transfer(param)
            self.out_c.write(":\n")
        self.out_c.write(' *\n')
        self.out_c.write(' * Undocumented.\n')
        self.out_c.write(' *\n')
        self.out_c.write(' * Returns:')
        self._write_annotation_transfer(func.retval)
        self.out_c.write('\n */')

    @contextmanager
    def _function(self, func):
        self._write_prototype(func)
        self._write_docs(func)
        self._write_prelude(self.out_c, func)
        self.out_c.write("\n{\n")
        yield
        self.out_c.write("}\n\n")

    def _codegen_start(self):
        warning = '/* GENERATED BY testcodegen.py; DO NOT EDIT */\n\n'
        self.out_h.write(warning)
        nsupper = self.namespace.name.upper()

        for header in self.include_first_header:
            self.out_h.write("""#include "%s"\n""" % header)

        self.out_h.write("""
#ifndef __%s_H__
#define __%s_H__

#include <glib-object.h>

""" % (nsupper, nsupper))

        for header in self.include_last_header:
            self.out_h.write("""#include "%s"\n""" % header)

        self.out_c.write(warning)

        for header in self.include_first_src:
            self.out_c.write("""#include "%s"\n""" % header)

        self.out_c.write("""#include "%s"\n\n""" % (self.out_h_filename, ))

        for header in self.include_last_src:
            self.out_c.write("""#include "%s"\n""" % header)

    def _codegen_end(self):
        self.out_h.write("""#endif\n""")

        self.out_h.close()
        self.out_c.close()

    def set_function_body(self, node, body):
        assert isinstance(node, ast.Function)
        self._function_bodies[node] = body

    def codegen(self):
        self.out_h = open(self.out_h_filename, 'w')
        self.out_c = open(self.out_c_filename, 'w')

        self._codegen_start()

        for node in self.namespace.values():
            if isinstance(node, ast.Function):
                with self._function(node):
                    body = self._function_bodies.get(node)
                    if not body:
                        body = ''
                    self.out_c.write(body)

        self._codegen_end()
