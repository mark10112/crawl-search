"""Detect incomplete generation; this is not an OCR accuracy score."""
import re
import unicodedata
from bs4 import BeautifulSoup

def excessive_repetition(text):
    plain=BeautifulSoup(text,'html.parser').get_text(' ')
    compact=re.sub(r'\s+','',plain)
    for match in re.finditer(r'(.{2,40}?)\1{19,}',compact):
        # Printed dot leaders / dashed empty table fields are real structure.
        # Repeated letters, marks and numbers still trigger the existing rule.
        semantic=any(unicodedata.category(c)[0] in 'LNM' for c in match.group(1))
        if semantic or len(match.group(0))>=1024:return True
    return False

def compact_markup(text):
    """Drop presentation attributes, never cells, spans, text or table structure."""
    # Parse only HTML fragments: parsing a whole Markdown document escapes '<'
    # in ordinary source text and can change paragraph whitespace.
    def compact(match):
        soup=BeautifulSoup(match.group(0),'html.parser')
        for tag in soup.find_all(True):
            tag.attrs={k:v for k,v in tag.attrs.items() if k in {'rowspan','colspan'}}
        return str(soup)
    return re.sub(r'<table\b[^>]*>.*?</table\s*>',compact,text,flags=re.I|re.S)

def completion_flags(text, generations):
    plain=BeautifulSoup(text,'html.parser').get_text(' ')
    flags=[]
    if any(g.get('repetition_guard') for g in generations):
        flags.append('Repetition guard cancelled recognition; incomplete text')
    if not generations or any(g.get('finish_reason') not in {'stop','eos_token'} for g in generations):
        flags.append('Recognition did not explicitly finish normally')
    if excessive_repetition(text):
        flags.append('Excessive repeated text')
    if len(plain.strip())<40:flags.append('Too little recognised text')
    if len(re.findall(r'<table\b',text,re.I))!=len(re.findall(r'</table\s*>',text,re.I)):
        flags.append('Unclosed table')
    return flags
