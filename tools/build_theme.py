"""Regenerate the presentation palette; processing code is untouched."""
from pathlib import Path
import json,re
ROOT=Path(__file__).resolve().parents[1]
def build():
    tokens=json.loads((ROOT/'design-tokens.json').read_text(encoding='utf-8'))
    target=ROOT/tokens['stylesheet']
    css=target.read_text(encoding='utf-8')
    block=':root{'+''.join('--'+k+':'+v+';' for k,v in tokens['css_variables'].items())+'}'
    css,count=re.subn(r':root\{[^}]*\}',lambda _:block,css,count=1)
    if count!=1:raise ValueError('Expected one root palette block')
    target.write_text(css,encoding='utf-8')
if __name__=='__main__':build()
