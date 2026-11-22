"""Network-free regression guard for the verified Div0 mirror identity.
Run alongside existing tests: python3 -m unittest discover -v -p 'test_*.py'
"""
import copy
import importlib.util
import json
import pathlib
import unittest

P = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location('refresh', P / 'refresh.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


class VerifiedMirror(unittest.TestCase):
    def setUp(self):
        self.events = json.loads((P / 'data/events.json').read_text())
        self.manual = next(e for e in json.loads((P / 'data/manual-events.json').read_text())
                           if e['id'] == 'manual-div0-secure-ai-20261124')
        self.cid = self.manual['same_event_as']['id']
        self.live = next(e for e in self.events if e['id'] == self.cid)
        self.alias = copy.deepcopy(self.manual)
        self.alias.setdefault('kind', 'manual')
        self.alias.setdefault('vendors', [])

    def merge(self, kept, old=None):
        r.merge_curated_events(kept, [copy.deepcopy(self.manual)], old or {}, '2026-11-22')
        return kept

    def test_real_pair_one_canonical_id_and_curated_note(self):
        old = {e['id']: copy.deepcopy(e) for e in self.events}
        old[self.manual['id']] = copy.deepcopy(self.alias)
        kept = self.merge(copy.deepcopy(old), old)
        self.assertEqual(len(kept), len(old) - 1)
        self.assertNotIn(self.manual['id'], kept)
        self.assertEqual(kept[self.cid]['note'], self.manual['note'])
        for field in ['id', 'url', 'start', 'end', 'venue', 'first_seen', 'last_seen']:
            self.assertEqual(kept[self.cid][field], self.live[field])
        self.assertEqual(set(old) - set(kept), {self.manual['id']})

    def test_repeat_daily_refresh_does_not_recreate_alias(self):
        old = {e['id']: copy.deepcopy(e) for e in self.events}
        old[self.manual['id']] = copy.deepcopy(self.alias)
        for _ in range(5):
            kept = copy.deepcopy(old)
            # Mirror the archive step, plus a freshly discovered canonical entry.
            kept[self.cid] = copy.deepcopy(self.live)
            kept[self.manual['id']] = copy.deepcopy(self.alias)
            old = self.merge(kept, old)
            self.assertNotIn(self.manual['id'], old)
            self.assertEqual(sum(e['url'] == self.live['url'] for e in old.values()), 1)
            self.assertEqual(old[self.cid]['source'].split('+').count('curated-annotations'), 1)
            self.assertEqual(old[self.cid]['note'], self.manual['note'])

    def test_fresh_canonical_schedule_wins_in_either_input_order(self):
        live = dict(self.live, start='2026-11-24T12:00:00Z', end='2026-11-24T14:00:00Z',
                    venue='Updated owning venue')
        for pair in [[self.alias, live], [live, self.alias]]:
            kept = self.merge({e['id']: copy.deepcopy(e) for e in pair})
            self.assertEqual(len(kept), 1)
            for f in ['start', 'end', 'venue']:
                self.assertEqual(kept[self.cid][f], live[f])

    def test_alias_only_and_empty_feed_fallback_use_same_canonical_id(self):
        for initial in [{self.alias['id']: copy.deepcopy(self.alias)}, {}]:
            kept = self.merge(initial)
            self.assertEqual(list(kept), [self.cid])
            self.assertEqual(kept[self.cid]['url'], self.live['url'])
            self.assertEqual(kept[self.cid]['note'], self.manual['note'])

    def test_undeclared_similar_title_different_url_not_removed(self):
        other = dict(self.live, id='distinct-session', url='https://lu.ma/distinct-session')
        kept = self.merge({self.cid: copy.deepcopy(self.live), other['id']: other})
        self.assertIn('distinct-session', kept)
        self.assertEqual(len(kept), 2)

    def test_canonical_url_alias_normalization(self):
        live = dict(self.live, id='new-live-id', url='https://luma.com/fzc6yw8r/?ref=calendar')
        kept = self.merge({self.alias['id']: copy.deepcopy(self.alias), live['id']: live})
        self.assertEqual(list(kept), [self.cid])
        self.assertEqual(kept[self.cid]['url'], self.live['url'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
