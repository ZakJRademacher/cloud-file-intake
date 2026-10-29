"""Create editable portfolio diagrams from verified project facts."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'deliverables'
OUT.mkdir(exist_ok=True)

base = '''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675">
<defs><pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0H0V40" fill="none" stroke="#203741" stroke-width=".65"/></pattern><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z" fill="#69dbc9"/></marker></defs>
<rect width="1200" height="675" fill="#0d1e28"/><rect width="1200" height="675" fill="url(#grid)"/>
<g font-family="Segoe UI,Arial,sans-serif"><rect x="48" y="45" width="5" height="24" rx="2" fill="#69dbc9"/><text x="68" y="64" fill="#94b6bd" font-size="15" letter-spacing="3">ZAK RADEMACHER / CLOUD ENGINEERING</text>'''
cover = base + '''
<text x="48" y="139" fill="#f2f5ef" font-size="57" font-weight="700" letter-spacing="-2">Cloud File Intake</text>
<text x="49" y="181" fill="#bed1d2" font-size="24">From a messy CSV to a traceable, checked result.</text>
<rect x="912" y="104" width="239" height="44" rx="22" fill="#163d3d" stroke="#3c7771"/><circle cx="935" cy="126" r="5" fill="#69dbc9"/><text x="951" y="133" fill="#a5f0df" font-size="16">VERIFIED ON AWS</text>
<g fill="#142c36" stroke="#34505c" stroke-width="1.5">
<rect x="48" y="241" width="244" height="153" rx="15"/><rect x="334" y="241" width="244" height="153" rx="15"/><rect x="620" y="241" width="244" height="153" rx="15"/><rect x="906" y="241" width="244" height="153" rx="15"/>
</g><g fill="#69dbc9" font-size="14" letter-spacing="2"><text x="69" y="273">01 / PRESERVE</text><text x="355" y="273">02 / QUEUE</text><text x="641" y="273">03 / CHECK</text><text x="927" y="273">04 / PUBLISH</text></g>
<g fill="#f2f5ef" font-size="29" font-weight="650"><text x="69" y="319">S3 upload</text><text x="355" y="319">SQS</text><text x="641" y="319">Python Lambda</text><text x="927" y="319">S3 results</text></g>
<g fill="#abc1c7" font-size="17"><text x="69" y="350">Private, versioned source</text><text x="355" y="350">Buffered events + retries</text><text x="641" y="350">Rules, review + reconciliation</text><text x="927" y="350">Files + final manifest</text><text x="69" y="376">Exact source identity</text><text x="355" y="376">Dead-letter destination</text><text x="641" y="376">Replay reuses the result</text><text x="927" y="376">Hashes checked on reuse</text></g>
<g stroke="#69dbc9" stroke-width="2" marker-end="url(#arrow)"><path d="M297 317H326"/><path d="M583 317H612"/><path d="M869 317H898"/></g>
<rect x="48" y="431" width="1102" height="151" rx="15" fill="#122730" stroke="#2e4c57"/>
<text x="71" y="465" fill="#95b9bd" font-size="14" letter-spacing="2">LIVE SAMPLE RECONCILIATION</text>
<g font-size="42" font-weight="700"><text x="71" y="522" fill="#f2f5ef">14</text><text x="283" y="522" fill="#69dbc9">6</text><text x="490" y="522" fill="#efb76c">7</text><text x="698" y="522" fill="#bacbd2">1</text><text x="903" y="522" fill="#f2f5ef">2,050</text></g>
<g fill="#a6c0c5" font-size="16"><text x="71" y="550">input rows</text><text x="283" y="550">accepted</text><text x="490" y="550">for review</text><text x="698" y="550">skipped repeat</text><text x="903" y="550">net cents</text></g>
<text x="49" y="628" fill="#a2bcc3" font-size="16">Python · Terraform · S3 · SQS · Lambda · IAM · CloudWatch</text><text x="1151" y="628" fill="#89a8b1" font-size="14" text-anchor="end">Independent project / Fictional data</text>
</g></svg>'''
(OUT / 'portfolio-cover.svg').write_text(cover, encoding='utf-8')
verification = base + '''
<text x="48" y="133" fill="#f2f5ef" font-size="49" font-weight="700" letter-spacing="-1">Every result needs evidence.</text>
<text x="49" y="176" fill="#bed1d2" font-size="23">Recorded AWS checks / October 29, 2026</text>
<rect x="48" y="222" width="690" height="366" rx="16" fill="#142c36" stroke="#34505c"/>
<g fill="#69dbc9" font-size="23"><text x="72" y="266">✓</text><text x="72" y="329">✓</text><text x="72" y="392">✓</text><text x="72" y="455">✓</text><text x="72" y="518">✓</text></g>
<g fill="#f2f5ef" font-size="23" font-weight="600"><text x="110" y="265">Live event delivery</text><text x="110" y="328">Exact output checks</text><text x="110" y="391">Safe replay</text><text x="110" y="454">Version-aware processing</text><text x="110" y="517">Clear file rejection</text></g>
<g fill="#abc1c7" font-size="17"><text x="110" y="290">S3 upload → SQS trigger → Lambda → S3 results</text><text x="110" y="353">All four CSV outputs match expected bytes and hashes</text><text x="110" y="416">Two upload versions, one content job, separate receipts</text><text x="110" y="479">Queued older and newer versions retain their own totals</text><text x="110" y="542">A schema error produces a quarantine diagnosis</text></g>
<rect x="768" y="222" width="382" height="366" rx="16" fill="#122730" stroke="#34505c"/>
<text x="792" y="264" fill="#95b9bd" font-size="14" letter-spacing="2">OPERATING BOUNDARIES</text>
<g fill="#f2f5ef" font-size="25" font-weight="600"><text x="792" y="313">1 MB / 5,000 rows</text><text x="792" y="397">Two queued jobs</text><text x="792" y="481">Private by design</text></g>
<g fill="#abc1c7" font-size="17"><text x="792" y="343">One complete CSV per job</text><text x="792" y="427">Maximum SQS trigger concurrency</text><text x="792" y="511">No public upload endpoint</text><text x="792" y="543">Local browser lab is a separate demo</text></g>
<text x="49" y="629" fill="#a2bcc3" font-size="16">Source, checks, infrastructure and recovery instructions travel together.</text>
<text x="1150" y="629" fill="#89a8b1" font-size="14" text-anchor="end">Fictional data / Defined sales contract</text>
</g></svg>'''
(OUT / 'verification-report.svg').write_text(verification, encoding='utf-8')
for name in ('portfolio-cover', 'verification-report'):
    (OUT / (name + '.html')).write_text('<!doctype html><html><head><meta charset="utf-8"><title>Cloud File Intake / '+name+'</title><style>html,body{margin:0;background:#0d1e28;width:1200px;height:675px}img{display:block}</style></head><body><img src="'+name+'.svg" width="1200" height="675" alt="Cloud File Intake project diagram"></body></html>',encoding='utf-8')
print('Editable project diagrams prepared.')
