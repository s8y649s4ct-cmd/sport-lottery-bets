#!/usr/bin/env python3
"""Pure local two-leg renderer. No network, secrets, grading, git, or deployment.
Default: validate only. --write: atomically replace HTML, preserving #results exactly.
Research timestamps come ONLY from reviewed JSON, never from rendering.
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal
from html import escape
import json
from pathlib import Path
import re
from urllib.parse import urlencode, urlsplit
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')
APP = 'https://sportsbook.fanduel.com/navigation/nfl'
ROOTS = {s: f'https://{s}.sportsbook.fanduel.com/' for s in ('pa','md')}

def require(ok, message):
    if not ok:
        raise ValueError(message)

def dt(s):
    v = datetime.fromisoformat(s)
    require(v.tzinfo is not None and v.utcoffset() is not None, 'Timestamp needs timezone')
    return v.astimezone(ET)

def fmt(s):
    v = dt(s) if isinstance(s, str) else s.astimezone(ET)
    return v.strftime('%b %-d, %Y · %-I:%M %p %Z')

def safe_url(s):
    p = urlsplit(s)
    require(p.scheme == 'https' and bool(p.hostname) and not p.username and not p.password, 'HTTPS public source URL required')
    require(not any(c in s for c in '\r\n\t'), 'Invalid URL characters')
    return s

def decimal(odds):
    require(type(odds) is int and odds != 0, 'American odds must be a nonzero integer')
    return Decimal(1) + (Decimal(100)/abs(odds) if odds < 0 else Decimal(odds)/100)

def total(card):
    return decimal(card['legs'][0]['american_odds']) * decimal(card['legs'][1]['american_odds'])

def ids(card):
    records = card.get('betslip_identifier_records', [])
    if not records:
        return False
    require(len(records) == 2, 'Need exactly two identifier records or none')
    for l, r in zip(card['legs'], records):
        require((r['sel'],r['event'],r['market']) == (l['team'],l['event'],l['market']), 'Identifier selection/event/market mismatch')
        require(dt(r['time']) == dt(l['start_at']), 'Identifier event time mismatch')
        require(l['event_key'] == r['event_key'], 'Independent event association mismatch')
        require(type(r['selectionId']) is int and r['selectionId'] > 0, 'Invalid selection ID')
        require(bool(r.get('source')) and bool(r.get('verification')), 'Missing identifier provenance')
        require(dt(r['captured_at']) <= dt(l['checked_at']), 'Identifier provenance timestamp in future')
        for state in ROOTS:
            require(bool(re.fullmatch(r'\d+\.\d+', str(r[state]))), 'Invalid/missing state market ID')
    return True

def slip(card, state):
    require(state in ROOTS and ids(card), 'Cannot create selection link without exact records')
    q = {}
    for i,r in enumerate(card['betslip_identifier_records']):
        q[f'marketId[{i}]'] = r[state]
        q[f'selectionId[{i}]'] = str(r['selectionId'])
    return 'https://sportsbook.fanduel.com/addToBetslip?' + urlencode(q)

def validate(data, now):
    require(data.get('schema_version') == 2, 'Expected reviewed schema_version=2')
    day = datetime.strptime(data['date'], '%Y-%m-%d').date()
    reviewed = dt(data['last_checked_at'])
    require(reviewed <= now, 'Research timestamp cannot be future')
    p = data['policies']
    require(0 < p['max_price_age_minutes'] <= 120 and 0 < p['max_review_age_minutes'] <= 75, 'Unsafe freshness policy')
    seen = set()
    for c in data['cards']:
        require(c['id'] not in seen and re.fullmatch('[a-z0-9-]+',c['id']), 'Invalid/duplicate card ID')
        seen.add(c['id'])
        require(c['status'] in ('conditional','ready','withdrawn'), 'Unknown card status')
        require(len(c['legs']) == 2, 'Every card must have EXACTLY two legs')
        require(c['legs'][0]['event_key'] != c['legs'][1]['event_key'] and c['legs'][0]['event'] != c['legs'][1]['event'], 'Same-game cards unsupported: independent events required')
        for l in c['legs']:
            require(dt(l['start_at']).date() == day, 'Leg not on shortlist local date')
            require(dt(l['checked_at']) <= reviewed and dt(l['availability_checked_at']) <= reviewed, 'Leg check after research timestamp')
            require(dt(l['price_quoted_at']) <= dt(l['checked_at']), 'Price quoted in future')
            decimal(l['american_odds'])
            require(all(l.get(k) for k in ('team','market','event','venue','evidence','remaining_checks','lineup_status')), 'Missing pick identity/rationale/risk')
            require(len(l.get('sources',[])) >= 2, 'At least two research citations required')
            for url in l['sources'] + [l['price_source'],l['schedule_source'],l['availability_source']]:
                safe_url(url)
        exact = ids(c)
        if c['status'] == 'ready':
            require(exact and all(l.get('price_state_verified') is True for l in c['legs']) and all(c.get(k) is True for k in ('availability_confirmed','price_live_verified','link_live_verified')), 'Ready status needs confirmed availability, live price and live links')
        # Guard against stale/hand-typed payout or selection links in reviewed source data.
        if 'theoretical_decimal_return' in c:
            require(abs(total(c)-Decimal(str(c['theoretical_decimal_return']))) < Decimal('0.00000001'), 'Stored payout conflicts with actual prices')
        if exact:
            for state in ROOTS:
                if 'betslip_link_'+state in c:
                    require(c['betslip_link_'+state] == slip(c,state), 'Stored betslip URL conflicts with source IDs')
    exposures = Counter(l['event_key'] for c in data['cards'] if c['status'] != 'withdrawn' for l in c['legs'])
    if any(v > 1 for v in exposures.values()):
        require(bool(data.get('shared_exposure_note')), 'Repeated-game exposure must be explicitly disclosed')
    return data

def deadline(card, data):
    p=data['policies']
    return min([dt(data['last_checked_at'])+timedelta(minutes=p['max_review_age_minutes'])] +
               [dt(l['checked_at'])+timedelta(minutes=p['max_review_age_minutes']) for l in card['legs']] +
               [dt(l['price_quoted_at'])+timedelta(minutes=p['max_price_age_minutes']) for l in card['legs']] +
               [dt(l['start_at']) for l in card['legs']])

def held_reason(c,d,now):
    if c['status']=='withdrawn': return c['status_reason']
    if d['date'] != now.astimezone(ET).date().isoformat(): return 'Not today in Eastern time; no longer staged.'
    if any(dt(l['start_at']) <= now for l in c['legs']): return 'At least one event has started; no longer a pregame card.'
    if deadline(c,d) <= now: return 'Research or reported price expired; fresh review required. Not staged.'
    return ''

def history(html):
    start=re.search(r'<section\s+id=[\"\x27]?results(?:[\"\x27]|\s|>)',html)
    require(start is not None, 'Missing #results: refusing to erase historical record')
    end=html.find('</section>',start.start())
    require(end>=0, 'Malformed history section')
    return html[start.start():end+len('</section>')]

def e(v): return escape(str(v),quote=True)

def sources(urls):
    labels={'www.nfl.com':'NFL','www.espn.com':'ESPN schedule','agentbets.ai':'Reported FanDuel odds','www.rotowire.com':'RotoWire — expected, not confirmed'}
    return '<span class="sources">Sources: '+' · '.join(f'<a href="{e(safe_url(u))}" rel="noopener">{e(labels.get(urlsplit(u).hostname,urlsplit(u).hostname))}</a>' for u in dict.fromkeys(urls))+'</span>'

def render_card(c,d,now,held=''):
    active=not held
    end=deadline(c,d).isoformat()
    h=f'<article id="{e(c["id"])}" class="two-leg-card" data-staged="{str(active).lower()}" data-review-until="{e(end)}" data-day="{e(d["date"])}"><h3>{e(c["title"])}</h3>'
    h+=f'<p class="card-status">{e("CONDITIONAL — not fully cleared" if active and c["status"]=="conditional" else "READY" if active else "NOT STAGED")}</p>'
    h+=f'<p>{e(held or c["status_reason"])}</p><p class="muted">{e(c.get("tier",""))}</p>'
    for i,l in enumerate(c['legs'],1):
        price=f'{l["american_odds"]:+d}'
        h+=f'<div class="leg"><h4>{i}. {e(l["team"])} · {e(l["market"])} {e(price)}</h4><p>{e(l["event"])}<br>{e(fmt(l["start_at"]))} · {e(l["venue"])}</p>'
        h+=f'<p><strong>Research reason:</strong> {e(l["evidence"])}</p><p><strong>Not yet resolved:</strong> {e(l["remaining_checks"])}</p><p class="muted">{e(l["lineup_status"])}</p>'
        h+=f'<p class="muted">Price snapshot: {e(fmt(l["price_quoted_at"]))}; reported, not live/state-verified. Research/availability checked: {e(fmt(l["checked_at"]))}. Earlier game-center/weather snapshots are not live.</p>'
        h+=sources(l['sources']+[l['price_source']])+'</div>'
    dec=total(c)
    h+=f'<p class="payout">Theoretical total return: {dec:.3f}× · $10 → ${dec*10:.2f} · $25 → ${dec*25:.2f} (includes stake).</p><p class="muted">Different-game decimal prices multiplied; not a FanDuel parlay quote. Raw price-derived joint implied probability: {Decimal(100)/dec:.1f}% (includes bookmaker margin; not a calibrated forecast, edge, or guarantee).</p>'
    if active:
        h+=f'<p class="muted">Needs a fresh review by {e(fmt(end))}, sooner if material news is detected. On-page clock disables this card after that deadline or kickoff; it does not monitor injuries or odds.</p><div class="b">'
        if ids(c):
            h+=f'<a class="fd-slip" href="{e(slip(c,"pa"))}" data-pa="{e(slip(c,"pa"))}" data-md="{e(slip(c,"md"))}">Try loading these 2 picks in FanDuel</a>'
        else:
            h+='<span class="notice">Exact selection IDs unavailable: app-only link, no preloaded picks.</span>'
        h+=f'<a class="fd-app secondary" href="{APP}">Open app only (no picks)</a><a class="fd secondary" href="{ROOTS["pa"]}" data-pa="{ROOTS["pa"]}" data-md="{ROOTS["md"]}">PA website fallback (not app prefill)</a></div>'
        if ids(c):
            captures='; '.join(sorted({fmt(r['captured_at']) for r in c['betslip_identifier_records']}))
            verification='Live selection acceptance verified; iPhone end-to-end prefill still untested.' if c.get('link_live_verified') else 'FanDuel live selection acceptance and iPhone prefill remain unverified.'
            h+=f'<p class="muted">Exact event/selection/market/time fields matched to attributed records captured {e(captures)}. {e(verification)} User-confirmed app opening is not proof of loaded selections. Check the actual two selections and price before any decision; opening this link does not place a wager.</p>'
    return h+'</article>'

def render(data,previous,now):
    validate(data,now)
    preserved=history(previous)
    active=[c for c in data['cards'] if not held_reason(c,data,now)]
    held=[c for c in data['cards'] if held_reason(c,data,now)]
    ready=sum(c['status']=='ready' for c in active)
    quote_reference=fmt(data['odds_reported_at_est']) if data.get('odds_reported_at_est') else 'none available'
    h='''<!doctype html><html lang="en" data-theme="light"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="apple-itunes-app" content="app-id=1413721906, app-argument=https://sportsbook.fanduel.com/navigation/nfl"><title>Sport Lottery Bets · Researched two-leg shortlist</title><link rel="stylesheet" href="two-leg.css"><script src="two-leg.js" defer></script></head><body><main><header><h1>Sport Lottery Bets</h1><div class="st" role="group" aria-label="Betslip market state; app still uses geolocation"><button type="button" data-s="pa">PA</button><button type="button" data-s="md">MD</button></div><button id="tg" type="button">Dark mode</button></header>'''
    h+=f'<div id="today-two-leg" data-publication="{e(data["date"])}"><h2>Researched two-leg shortlist · {e(data["date"])}</h2><p><strong id="current-count">{len(active)} staged: {ready} ready / {len(active)-ready} conditional.</strong> No guaranteed winners; no minimum number of cards or payout floor.</p><p>Last research check: <strong>{e(fmt(data["last_checked_at"]))}</strong>. Page rendered: {e(fmt(now))}.</p><p class="notice">Reported price reference: {e(quote_reference)}, not a live PA/MD quote. Probability takes priority over payout. These candidates have unresolved checks; missing confirmation is not treated as a prediction. No calibrated win forecast or positive expected value has been established. Even favorites lose; both legs must win.</p><p class="muted">Hourly scheduled review is not continuous monitoring. Detected material changes require a new researched publication; this page itself cannot detect them. PA/MD selects cached market IDs and website fallback, not app jurisdiction. FanDuel determines location/account eligibility. Universal links can open a browser in some contexts.</p><noscript><p class="notice">JavaScript is off: state defaults to PA and automatic expiry is unavailable. Do not use selection links after the printed review deadline or event start.</p></noscript><p id="expiry-note" role="status" aria-live="polite"></p>'
    h+='<p class="muted">'+e(data.get('shared_exposure_note','No shared legs or games across the staged cards. Different games reduce same-game dependence but do not prove statistical independence.'))+'</p>'
    h+=''.join(render_card(c,data,now) for c in active)
    if not active: h+='<p class="notice">No current cards passed the date, kickoff and freshness gates. Wait for a fresh researched update; do not substitute expired picks.</p>'
    h+='</div><section id="research-holds"><h2>Held / withdrawn — not additional recommendations</h2>'
    for c in held:
        h+=f'<details><summary>{e(c["title"])} — not staged</summary>'+render_card(c,data,now,held_reason(c,data,now))+'</details>'
    for r in data.get('research_holds',[]):
        h+=f'<details><summary>{e(r["title"])}</summary><p>{e(r["reason"])}</p>'+sources(r['sources'])+'</details>'
    h+='</section><section id="update-log"><h2>What changed</h2><ul>'
    for u in data.get('update_log',[]): h+=f'<li>{e(fmt(u["at"]))}: {e(u["text"])}</li>'
    h+='</ul><p class="muted">Research cards are not placed wagers. Historical results below are preserved unchanged; no outcome is inferred from this shortlist. Legacy totals may include overlapping cards/repeated legs and are not an independent, calibrated track record.</p></section>'+preserved
    h+='''<footer>21+ · Gambling involves risk. Nothing here ensures a win. No wagers are placed by this site.<br><a href="https://apps.apple.com/us/app/fanduel-sportsbook-casino/id1413721906">Official iPhone app listing</a> · <a href="https://the-odds-api.com/releases/deep-links.html">Link-format documentation</a> · <a href="https://sportsbook.fanduel.com/.well-known/apple-app-site-association">Apple app association</a></footer></main></body></html>'''
    require(history(h)==preserved,'Historical record changed')
    return h+'\n'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,required=True)
    p.add_argument('--output',type=Path,default=Path('docs/index.html'))
    p.add_argument('--write',action='store_true',help='Write rendered HTML; never commit/push')
    p.add_argument('--check',action='store_true',help='Validate only (default)')
    args=p.parse_args()
    require(not(args.write and args.check),'Choose --check OR --write')
    now=datetime.now(ET)
    data=json.loads(args.data.read_text())
    old=args.output.read_text()
    result=render(data,old,now)
    n=sum(not held_reason(c,data,now) for c in data['cards'])
    if args.write:
        tmp=args.output.with_suffix('.html.tmp')
        tmp.write_text(result)
        tmp.replace(args.output)
    print(f'{"WROTE" if args.write else "CHECKED"}: {n} staged / {len(data["cards"])-n} held; history preserved; no network/deployment')

if __name__=='__main__':
    main()
