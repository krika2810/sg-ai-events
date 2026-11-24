"""Reconstructed provenance regression. Tests the observed stacking defect and its fix."""
import importlib.util, subprocess, tempfile
from pathlib import Path
TODAY='2026-11-22'
MANUAL=[dict(id='evt-manual-1',url='https://lu.ma/sampleai',name='Sample AI Meetup',start='2026-12-01T10:00:00+00:00',source='manual',kind='manual',note='independently checked')]
def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def check(label,ok):
 print(f"  [{'PASS' if ok else 'FAIL'}] {label}");return ok
def cycle(mod,old):
 kept={k:dict(v) for k,v in old.items() if v.get('kind')!='luma'}
 mod.merge_curated_events(kept,[dict(e) for e in MANUAL],old,TODAY);return kept
def main():
 root=Path(__file__).parent;current=load(root/'refresh.py','current')
 # Extract the known prior implementation from the repository commit where regression was observed.
 old_source=subprocess.check_output(['git','show','d39d6d6:refresh.py'],cwd=root,text=True)
 with tempfile.TemporaryDirectory() as d:
  oldpath=Path(d)/'old.py';oldpath.write_text(old_source);old=load(oldpath,'old')
  prior={e['id']:dict(e) for e in MANUAL}
  for _ in range(5):prior=cycle(old,prior)
  ok=check('pre-fix reproduction stacks suffix',prior['evt-manual-1']['source'].count('curated-annotations')>1)
  live={'evt-live-1':dict(id='evt-live-1',url='https://lu.ma/sampleai',kind='luma',source='cal:SomeCal+curated-annotations',first_seen='2026-11-01')}
  old.merge_curated_events(live,[dict(MANUAL[0])],live,TODAY)
  ok &= check('pre-fix live match gains another suffix',live['evt-live-1']['source'].count('curated-annotations')>1)
 for label,mod in [('fixed',current)]:
  events={e['id']:dict(e) for e in MANUAL}
  for _ in range(5):events=cycle(mod,events)
  src=events['evt-manual-1']['source'];ok &= check('manual event has one suffix after five cycles',src.count('curated-annotations')==1)
  ok &= check('original provenance remains',src.startswith('manual'))
  ok &= check('curated note remains',events['evt-manual-1'].get('note')=='independently checked')
  live={'evt-live-1':dict(id='evt-live-1',url='https://lu.ma/sampleai',kind='luma',source='cal:SomeCal+curated-annotations',first_seen='2026-11-01')}
  mod.merge_curated_events(live,[dict(MANUAL[0])],live,TODAY)
  src=live['evt-live-1']['source'];ok &= check('live match has one suffix',src.count('curated-annotations')==1)
  ok &= check('live source base preserved',src.startswith('cal:SomeCal'))
  ok &= check('distinct source values remain combinable',mod.with_source('cal:X+cal:Y','cal:Z')=='cal:X+cal:Y+cal:Z')
  ok &= check('empty provenance handled',mod.with_source('','curated-annotations')=='curated-annotations')
  ok &= check('already single suffix unchanged',mod.with_source('manual+curated-annotations','curated-annotations')=='manual+curated-annotations')
  ok &= check('same feed input does not add suffix',mod.with_source('cal:X','cal:X')=='cal:X')
 return 0 if ok else 1
raise SystemExit(main())
