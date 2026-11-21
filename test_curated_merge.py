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
class SGInnovateSchedule(unittest.TestCase):
 def test_explicit_end_time_not_assumed_duration(self):
  x=r.sginnovate_schedule('<section class="schedule">Date: 24 Nov 2026 Time: 7:00 PM - 9:30 PM Location: 47 Hill St, Singapore 179365</section>');self.assertEqual(x[1].hour,21);self.assertEqual(x[1].minute,30)
 def test_foreign_physical_rejected_despite_sg_footer(self):
  self.assertIsNone(r.sginnovate_schedule('<section class="schedule">Date: 01 Dec 2026 Time: 10:30 AM - 5:50 PM Location: Kuala Lumpur Convention Centre, Malaysia</section><footer>Singapore</footer>'))
 def test_missing_clocks_not_invented(self):
  self.assertIsNone(r.sginnovate_schedule('<section class="schedule">Start Date: 21 Nov 2026 End Date: 26 Nov 2026 Location: Singapore</section>'))
 def test_online_requires_actual_location(self):
  x=r.sginnovate_schedule('<section class="schedule">Date: 24 Nov 2026 Time: 7:00 PM - 9:00 PM Location: Google Meet</section>');self.assertTrue(x[3]);self.assertFalse(x[4])
 def test_invalid_or_reverse_clock_rejected(self):
  self.assertIsNone(r.sginnovate_schedule('<section class="schedule">Date: 24 Nov 2026 Time: 9:00 PM - 7:00 PM Location: Singapore</section>'))
 def test_same_sginnovate_url(self):
  self.assertEqual(r.event_url_key('https://www.sginnovate.com/event/example'),r.event_url_key('https://sginnovate.com/event/example'))
class UnknownEnd(unittest.TestCase):
 def test_amd_structured_end_retains_visible_uncertainty(self):
  es=json.loads((P/'data/events.json').read_text());e=next(x for x in es if x['id']=='manual-amd-ai-league-2026');self.assertEqual(e['end'],'2026-12-01T19:00:00Z');self.assertTrue(e['end_unconfirmed']);self.assertEqual(e['schedule_review_due'],'2026-11-29');self.assertIn('through December',e['note']);self.assertIn('DeepLearning.AI Pro',e['credits']);self.assertIn('eligibility, duration or redemption terms',e['credits']);self.assertNotIn('Nov 14',e['credits'])
 def test_review_date_is_not_expiry(self):
  e=next(x for x in json.loads((P/'data/events.json').read_text())if x['id']=='manual-concordium-trusted-agents-2026');self.assertEqual(e['schedule_review_due'],'2026-11-29');self.assertNotEqual(e.get('end'),e['schedule_review_due'])
 def test_live_confirmed_end_clears_uncertainty(self):
  manual=dict(id='id',url='https://luma.com/x',end=None,end_unconfirmed=True,schedule_review_due='2026-11-22');kept={'id':dict(id='id',url='https://lu.ma/x',end='2026-12-05T10:00:00Z',source='live')};r.merge_curated_events(kept,[manual],{},'2026-11-21');self.assertEqual(kept['id']['end'],'2026-12-05T10:00:00Z');self.assertNotIn('end_unconfirmed',kept['id'])
class PlanningCaveats(unittest.TestCase):
 def test_ai_governance_registration_closed_note(self):
  es=json.loads((P/'data/events.json').read_text());e=next(x for x in es if x['id']=='evt-JUcqkT7kGgvIS7Y');self.assertIn('registration was closed',e['note']);self.assertIn('Google Meet',e['note']);self.assertTrue(e['virtual'])
 def test_concordium_deadline_separate(self):
  e=next(x for x in json.loads((P/'data/events.json').read_text())if x['id']=='manual-concordium-trusted-agents-2026');self.assertEqual(e['submission_deadline'],'2026-12-09T23:59:00+00:00');self.assertIsNone(e['end']);self.assertTrue(e['end_unconfirmed']);self.assertIn('Judging',e['note']);self.assertIn('7:59 AM SGT',e['note'])
 def test_claude_prerequisite_persists(self):
  es=json.loads((P/'data/manual-events.json').read_text());e=next(x for x in es if x['id']=='evt-GVGgTzF2xmBQris');kept={e['id']:dict(e,kind='luma',source='live',note='')};r.merge_curated_events(kept,[e],{e['id']:e},'2026-11-22');self.assertIn('paid Claude Pro',kept[e['id']]['note']);self.assertIn('Free to attend',kept[e['id']]['note'])
if __name__=='__main__':unittest.main(verbosity=2)
