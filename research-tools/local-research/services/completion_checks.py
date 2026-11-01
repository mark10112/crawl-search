"""Detect incomplete generation; this is not an OCR accuracy score."""
import re
from bs4 import BeautifulSoup

def completion_flags(text, generations):
    plain=BeautifulSoup(text,'html.parser').get_text(' ')
    flags=[]
    if not generations or any(g.get('finish_reason') not in {'stop','eos_token'} for g in generations):
        flags.append('Recognition did not explicitly finish normally')
    if re.search(r'(.{2,40}?)\1{19,}',re.sub(r'\s+','',plain)):
        flags.append('Excessive repeated text')
    if len(plain.strip())<40:flags.append('Too little recognised text')
    if len(re.findall(r'<table\b',text,re.I))!=len(re.findall(r'</table\s*>',text,re.I)):
        flags.append('Unclosed table')
    return flags
