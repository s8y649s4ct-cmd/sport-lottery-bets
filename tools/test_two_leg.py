#!/usr/bin/env python3
"""Offline standard-library regression suite. Run from repository root."""
import copy
from datetime import datetime, timedelta
from decimal import Decimal
import json
from pathlib import Path
import unittest
from urllib.parse import parse_qs,urlsplit
import render_two_leg as r

D=json.loads(Path('tools/fixtures/two-leg-2026-11-08.json').read_text())
HTML=Path('docs/index.html').read_text()
NOW=r.dt(D['last_checked_at'])+timedelta(seconds=1)

class SafetyTests(unittest.TestCase):
    def test_valid_and_retained(self):
        r.validate(D,NOW)
        self.assertEqual([c['title'] for c in D['cards'] if not r.held_reason(c,D,NOW)],['Lions + Texans','Rams + Broncos'])
    def test_every_card_two_legs(self):
        for n in (1,3):
            d=copy.deepcopy(D);d['cards'][0]['legs']=(d['cards'][0]['legs']*2)[:n]
            with self.assertRaisesRegex(ValueError,'EXACTLY'):r.validate(d,NOW)
    def test_same_game_rejected(self):
        d=copy.deepcopy(D);c=d['cards'][0];c['legs'][1]['event_key']=c['legs'][0]['event_key']
        with self.assertRaisesRegex(ValueError,'Same-game'):r.validate(d,NOW)
    def test_wrong_local_day(self):
        d=copy.deepcopy(D);d['cards'][0]['legs'][0]['start_at']='2026-11-09T13:00:00-05:00'
        with self.assertRaisesRegex(ValueError,'shortlist local date'):r.validate(d,NOW)
    def test_future_research(self):
        with self.assertRaisesRegex(ValueError,'future'):r.validate(D,r.dt(D['last_checked_at'])-timedelta(seconds=1))
    def test_naive_timestamps(self):
        with self.assertRaisesRegex(ValueError,'timezone'):r.dt('2026-11-08T08:00:00')
    def test_bad_id_and_mismatch(self):
        for key,value in [('selectionId',0),('pa','742.fake'),('sel','Wrong Team'),('time','2026-11-08T20:00:00+00:00'),('event_key','wrong')]:
            d=copy.deepcopy(D);d['cards'][0]['betslip_identifier_records'][0][key]=value
            with self.assertRaises(ValueError):r.validate(d,NOW)
    def test_no_ids_app_only(self):
        d=copy.deepcopy(D);c=d['cards'][0];c['betslip_identifier_records']=[]
        r.validate(d,NOW);out=r.render_card(c,d,NOW)
        self.assertNotIn('class="fd-slip"',out)
        self.assertIn('app-only link, no preloaded picks',out)
        self.assertIn('class="fd-app secondary"',out)
    def test_two_correct_state_pairs(self):
        for c in D['cards']:
            for state in ('pa','md'):
                q=parse_qs(urlsplit(r.slip(c,state)).query)
                self.assertEqual(len(q),4)
                for i,rec in enumerate(c['betslip_identifier_records']):
                    self.assertEqual(q[f'marketId[{i}]'],[rec[state]])
                    self.assertEqual(q[f'selectionId[{i}]'],[str(rec['selectionId'])])
    def test_price_math_and_positive_odds(self):
        self.assertEqual(r.decimal(150),Decimal('2.5'));self.assertEqual(r.decimal(-200),Decimal('1.5'))
        self.assertEqual([f'{r.total(c)*10:.2f}' for c in D['cards']],['18.97','22.90','24.02'])
        self.assertEqual([f'{r.total(c)*25:.2f}' for c in D['cards']],['47.42','57.26','60.05'])
        for odd in (0, float('nan'),True):
            with self.assertRaises(ValueError):r.decimal(odd)
    def test_fake_payout_and_url(self):
        for field,value in [('theoretical_decimal_return',10),('betslip_link_pa','https://example.com/fake')]:
            d=copy.deepcopy(D);d['cards'][0][field]=value
            with self.assertRaises(ValueError):r.validate(d,NOW)
    def test_started_and_stale_and_wrong_today_are_held(self):
        c=D['cards'][0]
        self.assertIn('started',r.held_reason(c,D,r.dt(c['legs'][0]['start_at'])))
        self.assertIn('expired',r.held_reason(c,D,r.dt('2026-11-08T09:00:00-05:00')))
        later=r.render(D,HTML,r.dt('2026-11-09T08:00:00-05:00'))
        self.assertNotIn('class="fd-slip"',later);self.assertIn('No current cards passed',later)
    def test_review_expiration_even_if_quote_fresh(self):
        d=copy.deepcopy(D);c=d['cards'][0]
        for l in c['legs']:l['price_quoted_at']=d['last_checked_at']
        self.assertIn('expired',r.held_reason(c,d,r.dt(d['last_checked_at'])+timedelta(minutes=76)))
    def test_withdrawn_no_load_buttons(self):
        c=D['cards'][1];out=r.render_card(c,D,NOW,r.held_reason(c,D,NOW))
        self.assertNotIn('class="fd-slip"',out)
    def test_ready_cannot_be_asserted(self):
        d=copy.deepcopy(D);d['cards'][0]['status']='ready'
        with self.assertRaisesRegex(ValueError,'Ready status'):r.validate(d,NOW)
    def test_exposure_disclosure(self):
        d=copy.deepcopy(D);c=copy.deepcopy(d['cards'][0]);c['id']='repeat';d['cards'].append(c)
        with self.assertRaisesRegex(ValueError,'exposure'):r.validate(d,NOW)
        d['shared_exposure_note']='Explicit test fixture repeat, not a new recommendation.';r.validate(d,NOW)
    def test_history_preserved_and_idempotent(self):
        out=r.render(D,HTML,NOW)
        self.assertEqual(r.history(out),r.history(HTML))
        self.assertEqual(out,r.render(D,out,NOW))
        with self.assertRaisesRegex(ValueError,'history|results'):r.render(D,'<html></html>',NOW)
    def test_escapes_research_text(self):
        d=copy.deepcopy(D);d['cards'][0]['legs'][0]['evidence']='<script>evil()</script>'
        out=r.render(d,HTML,NOW)
        self.assertIn('&lt;script&gt;evil()',out);self.assertNotIn('<script>evil()',out)
    def test_sources_https_only(self):
        d=copy.deepcopy(D);d['cards'][0]['legs'][0]['sources'][0]='javascript:evil()'
        with self.assertRaisesRegex(ValueError,'HTTPS'):r.validate(d,NOW)
    def test_empty_day_no_invented_quote(self):
        d=copy.deepcopy(D);d['cards']=[];d['odds_reported_at_est']=None
        out=r.render(d,HTML,NOW)
        self.assertIn('No current cards passed',out);self.assertIn('none available',out);self.assertNotIn('class="fd-slip"',out)
    def test_mobile_and_no_legacy_import(self):
        css=Path('docs/two-leg.css').read_text();self.assertIn('@media(max-width:480px)',css);self.assertIn('overflow-x:auto',css)
        source=Path('tools/render_two_leg.py').read_text();self.assertNotIn('import build',source);self.assertNotIn('subprocess',source)

if __name__=='__main__':unittest.main(verbosity=2)
