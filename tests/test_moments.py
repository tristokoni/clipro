import unittest

from captions import motion_states
from moments import cue_groups, pick_moments


class MomentTests(unittest.TestCase):
    def test_candidates_use_full_recording_and_sentence_boundaries(self):
        rows = [dict(start=minute * 60 + i * 5, end=minute * 60 + i * 5 + 4.8,
                     text="Prečo na tom záleží?" if i == 0 else "Toto je pokračovanie myšlienky.")
                for minute in range(60) for i in range(9)]
        for target in (15, 30, 60):
            picks = sorted(pick_moments(rows, target), key=lambda m: m['start'])
            self.assertEqual(len(picks), 5)
            self.assertGreater(picks[-1]['start'], 1800)
            for first, second in zip(picks, picks[1:]):
                self.assertLessEqual(first['end'], second['start'])
            for item in picks:
                self.assertGreaterEqual(item['end']-item['start'], target*.5)
                self.assertLessEqual(item['end']-item['start'], target*1.45)
                self.assertIn(item['end'], {r['end'] for r in rows})
        self.assertEqual(pick_moments([]), [])

    def test_word_highlight_follows_local_timing(self):
        words = [dict(text='Žltý', start=4, end=4.6), dict(text='dážď.', start=4.6, end=5)]
        row, = cue_groups(words)
        states = list(motion_states(row,'karaoke'))
        self.assertEqual([(s[0],s[1],s[3]) for s in states], [(4,4.6,0),(4.6,5,1)])
        pop=list(motion_states(row,'pop'))
        self.assertGreater(max(s[4] for s in pop), 1)
        self.assertEqual(pop[-1][1], 5)
