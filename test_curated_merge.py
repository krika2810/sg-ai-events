import unittest,importlib.util,copy,json,pathlib
P=pathlib.Path(__file__).parent
s=importlib.util.spec_from_file_location('refresh',P/'refresh.py');r=importlib.util.module_from_spec(s);s.loader.exec_module(r)
class CuratedMerge(unittest.TestCase):
 def setUp(self):
  self.live=dict(id='live-id',url='https://lu.ma/same',name='Changed official title',start='2026-12-02T10:00:00Z',end='2026-12-02T13:00:00Z',venue='New live venue',sg=True,virtual=False,kind='luma',source='live',first_seen='2026-11-21',last_seen='2026-11-21')
  self.manual=dict(id='manual-stable-id',url='https://luma.com/same/',name='Old title',start='2025-01-01T00:00:00Z',end='2025-01-01T01:00:00Z',venue='Old stale venue',sg=False,virtual=True,note='Checked condition',fee='S$35',fee_label='Paid event',curated_location_note='Check ticket: venue disagreement',annotation_checked_at='2026-11-20',annotation_sources=['https://luma.com/same'])
 def merge(self,manual=None,old=None):
  kept={'live-id':copy.deepcopy(self.live)};r.merge_curated_events(kept,[manual or self.manual],old or {},'2026-11-21');return next(iter(kept.values()))
 def test_live_schedule_location_win(self):
  e=self.merge()
  for k in ['start','end','venue','sg','virtual','name','last_seen']:self.assertEqual(e[k],self.live[k])
 def test_annotation_and_source_dates_preserved(self):
  e=self.merge()
  for k in ['note','fee','fee_label','curated_location_note','annotation_checked_at','annotation_sources']:self.assertEqual(e[k],self.manual[k])
 def test_existing_id_and_first_seen_stay(self):
  old={'manual-stable-id':dict(self.manual,first_seen='2026-11-06')};e=self.merge(old=old);self.assertEqual(e['id'],'manual-stable-id');self.assertEqual(e['first_seen'],'2026-11-06')
 def test_new_live_id_remains_when_no_prior(self):self.assertEqual(self.merge()['id'],'live-id')
 def test_luma_aliases_query_and_case(self):self.assertEqual(r.event_url_key('https://lu.ma/AbC/?foo=x'),r.event_url_key('https://luma.com/abc'))
 def test_non_luma_domains_not_conflated(self):self.assertNotEqual(r.event_url_key('https://other.com/same'),r.event_url_key('https://lu.ma/same'))
 def test_title_prefix_never_deletes_distinct(self):
  m=dict(self.manual,url='https://lu.ma/different',id='second',name=self.live['name'],start=self.live['start']);k={'live-id':self.live.copy()};r.merge_curated_events(k,[m],{},'2026-11-21');self.assertEqual(len(k),2)
 def test_manual_only_preserves_verification_date(self):
  k={};m=dict(self.manual,last_seen='2026-11-06');r.merge_curated_events(k,[m],{},'2026-11-21');self.assertEqual(next(iter(k.values()))['last_seen'],'2026-11-06')
 def test_real_voice_and_trivia_annotations(self):
  es=json.loads((P/'data/manual-events.json').read_text());manual=[e for e in es if e['id']in ['evt-h4LRoWZJwR7H3Bb','evt-cDvxGxlGoWXA0Vn']];k={}
  for e in manual:k[e['id']]=dict(e,kind='luma',source='live',start='2027-01-01T01:00:00Z',venue='Fresh live venue',note='',fee='')
  r.merge_curated_events(k,manual,{e['id']:e for e in manual},'2026-11-22');self.assertEqual(len(k),2)
  voice=k['evt-h4LRoWZJwR7H3Bb'];trivia=k['evt-cDvxGxlGoWXA0Vn'];self.assertIn('73B',voice['curated_location_note']);self.assertIn('hotspot',voice['note']);self.assertIn('35',trivia['fee']);self.assertEqual(voice['start'],'2027-01-01T01:00:00Z');self.assertEqual(voice['annotation_checked_at'],'2026-11-21T18:51:00+08:00')
if __name__=='__main__':unittest.main(verbosity=2)
