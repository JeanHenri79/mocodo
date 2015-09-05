#!/usr/bin/env python
# encoding: utf-8

import codecs
import time
from relations import Relations
from version_number import version
import os
import sys
import json
import re

def safe_print_for_PHP(s):
    """ It seems that when called from PHP, Python is unable to guess correctly
        the encoding of the standard output. """
    try:
        print >> sys.stdout, s
    except UnicodeEncodeError:
        print >> sys.stdout, s.encode("utf8")


class Common:

    def __init__(self, params):
        self.params = params

    def output_success_message(self, path):
        return _('Output file "{filename}" successfully generated.').format(filename=path)

    def timestamp(self):
        return _("Generated by Mocodo {version} on {date}").format(version=version, date=time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime()))

    def load_input_file(self):
        for encoding in self.params["encodings"]:
            try:
                self.encoding = encoding
                return codecs.open(self.params["input"], encoding=encoding).read().replace('"', '').split("\n")
            except UnicodeError:
                pass
        raise RuntimeError(("Mocodo Err.5 - " + _('Unable to read "{filename}" with any of the following encodings: "{encodings}".').format(filename=self.params["input"], encodings= ", ".join(self.params["encodings"])).encode("utf8")))

    def load_style(self):
        
        def load_by_name(name):
            path = self.params[name] + ("" if self.params[name].endswith(".json") else ".json") 
            if os.path.exists(path):
                try:
                    return json.loads(codecs.open(path, "r", "utf8").read())
                except:
                    raise RuntimeError(("Mocodo Err.3 - " + _('Problem with "{name}" file "{path}.json".').format(name=name, path=path)).encode("utf8"))
            path = os.path.join(self.params["script_directory"], name, path)
            try:
                return json.loads(codecs.open(path, "r", "utf8").read())
            except:
                raise RuntimeError(("Mocodo Err.3 - " + _('Problem with "{name}" file "{path}.json".').format(name=name, path=path)).encode("utf8"))
        
        style = {}
        style.update(load_by_name("colors"))
        style.update(load_by_name("shapes"))
        style["transparent_color"] = None
        return style

    def dump_output_file(self, result):
        path = "%(output_name)s_%(image_format)s.py" % self.params
        codecs.open(path, "w", encoding="utf8").write(result)
        safe_print_for_PHP(self.output_success_message(path))

    def dump_mld_files(self, relations):
        relation_templates = []
        for relation_template in self.params["relations"]:
            try:
                path = os.path.join(self.params["script_directory"], "relation_templates", "%s.json" % relation_template)
                contents = json.loads(codecs.open(path, "r", "utf8").read())
                relation_templates.append(contents)
            except:
                safe_print_for_PHP(_('Problem with template {template}.').format(template=relation_template + ".json"))
        for relation_template in relation_templates:
            path = os.path.join(self.params["output_name"] + relation_template["extension"])
            try:
                text = relations.get_text(relation_template)
                safe_print_for_PHP(self.output_success_message(path))
            except:
                text = _("Problem during the generation of the relational schema.")
                safe_print_for_PHP(text)
                raise
            codecs.open(path, "w", encoding="utf8").write(text)

    def process_geometry(self, mcd, style):
        
        def dump_geo_file(d):
            try:
                path = "%(output_name)s_geo.json" % self.params
                codecs.open(path, "w", "utf8").write(json.dumps(d, ensure_ascii=False))
                safe_print_for_PHP(self.output_success_message(path))
            except IOError:
                safe_print_for_PHP(_('Unable to generate file "{filename}"!').format(filename=os.path.basename(path)))
        
        l = [
            ("size", (mcd.w, mcd.h)),
            ("cx", [(box.name, box.x + box.w / 2) for row in mcd.rows for box in row if box.kind != "phantom"]),
            ("cy", [(box.name, box.y + box.h / 2) for row in mcd.rows for box in row if box.kind != "phantom"]),
            ("k", [(leg.identifier(), leg.value()) for row in mcd.rows for box in row for leg in box.legs]),
            ("t", [(leg.identifier(), 0.5) for row in mcd.rows for box in row for leg in box.legs if leg.arrow]),
            ("colors", [((c, style[c]) if style[c] else (c, None)) for c in sorted(style.keys()) if c.endswith("_color")]),
        ]
        if self.params.get("extract"): # Generate a separated JSON file for the geometry
            dump_geo_file(dict(l))
            result = []
            result.append("import json")
            result.append("")
            result.append("geo = json.loads(open('%(output_name)s_geo.json').read())" % self.params)
            result.append("(width,height) = geo.pop('size')")
            result.append("for (name, l) in geo.iteritems(): globals()[name] = dict(l)")
        else: # include the geometry at the beginning of the generated Python file
            result = ["(width,height) = (%s,%s)" % l.pop(0)[1]]
            for (identifier, items) in l:
                if items: # pretty print the dictionnary
                    s = "%%-%ss" % (max(len(k) for (k, _) in items) + 3)
                    result.append("%s = {\n    %s\n}" % (identifier, "\n    ".join(["%s: %s," % (s % ('u"%s"' % k), ("%4d" % v if type(v) is int else ("% .2f" % v if type(v) is float else repr(v)))) for (k, v) in items])))
        return result
