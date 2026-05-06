from django import template
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

register = template.Library()


@register.filter
def pygmentize(code, lang):
    if code is not None:
        try:
            lexer = get_lexer_by_name(lang, stripall=True, startinline=True)
        except ClassNotFound:
            lexer = get_lexer_by_name("text")
        formatter = HtmlFormatter(style="colorful", cssclass="highlight", lineanchors="line")
        return highlight(code, lexer, formatter)
    else:
        return code
