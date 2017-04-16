# coding: utf-8

"""
    Strips down all unsupported Telegram HTML.
    :copyright: (c) 2017 by Kyraminol.
"""

import mistune

class SimplestRenderer(mistune.Renderer):
    def block_quote(self, text):
        return text

    def block_code(self, code, lang=None):
        return '<pre>%s\n</pre>\n' % code

    def footnote_item(self, key, text):
        return text

    def footnote_ref(self, key, index):
        return index

    def footnotes(self, text):
        return text

    def header(self, text, level, raw=None):
        return ("%s%s") % ("#" * level, text)

    def hrule(self):
        return ""

    def image(self, src, title, text):
        return text

    def linebreak(self):
        return

    def list(self, body, ordered=True):
        return body

    def list_item(self, text):
        return text

    def newline(self):
        return "\n"

    def paragraph(self, text):
        return text

    def strikethrough(self, text):
        return text

    def table(self, header, body):
        return "%s%s" % (header,body)

    def table_cell(self, content, **flags):
        return content

    def table_row(self, content):
        return content

