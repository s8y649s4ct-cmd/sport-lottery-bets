'use strict';
// Offline DOM/clock harness; not an iPhone or live sportsbook acceptance test.
const fs=require('fs'), vm=require('vm'), assert=require('assert');
const data=JSON.parse(fs.readFileSync('tools/fixtures/two-leg-2026-11-08.json','utf8'));
const source=fs.readFileSync('docs/two-leg.js','utf8');
class Element {
  constructor(attrs={}) {this.attrs={...attrs};this.dataset={};for(const [k,v] of Object.entries(attrs))if(k.startsWith('data-'))this.dataset[k.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=v;this.listeners={};this.textContent='';this.hidden=false;this.classList={toggle:(k,v)=>{this[k]=v;}};this.links=[];}
  setAttribute(k,v){this.attrs[k]=v;} removeAttribute(k){delete this.attrs[k];} getAttribute(k){return this.attrs[k];} hasAttribute(k){return k in this.attrs;}
  set href(v){this.attrs.href=v;} get href(){return this.attrs.href;}
  addEventListener(k,f){this.listeners[k]=f;} querySelectorAll(){return this.links;} querySelector(){return {textContent:'CONDITIONAL'};}
  click(){const event={prevented:false,preventDefault(){this.prevented=true;}};this.listeners.click?.(event);return event;}
}
function run(storageFails=false) {
 let clock=Date.parse(data.last_checked_at)+1000, tick;
 const cards=data.cards.filter(c=>c.status!=='withdrawn').map(c=>{
   const card=new Element({'data-review-until':'2026-11-08T09:00:00-05:00','data-day':data.date});
   const a=new Element({'href':c.betslip_link_pa,'data-pa':c.betslip_link_pa,'data-md':c.betslip_link_md});card.links=[a];return card;
 });
 const buttons=['pa','md'].map(s=>new Element({'data-s':s}));
 const fallback=new Element({'data-pa':'https://pa.sportsbook.fanduel.com/','data-md':'https://md.sportsbook.fanduel.com/'});
 const app=new Element({href:data.app_link});const els={tg:new Element(),'expiry-note':new Element(),'current-count':new Element()};const root={dataset:{}};
 const document={documentElement:root,getElementById:id=>els[id],querySelectorAll:s=>({'[data-s]':buttons,'a.fd':[fallback],'.two-leg-card[data-staged="true"]':cards,'a.fd-slip':cards.flatMap(c=>c.links)})[s]||[]};
 class Clock extends Date {constructor(v){super(v===undefined?clock:v);}static now(){return clock;}}
 const localStorage={getItem:()=>{if(storageFails)throw Error('storage denied');return null;},setItem:()=>{if(storageFails)throw Error('storage denied');}};
 vm.runInNewContext(source,{document,localStorage,Date:Clock,Intl,Number,setInterval:f=>{tick=f;}});
 assert.equal(root.dataset.theme,'light');assert.equal(els['current-count'].textContent,'2 staged: 0 ready / 2 conditional.');
 for(const c of cards)assert.equal(c.links[0].href,c.links[0].dataset.pa);
 buttons[1].click();assert.equal(fallback.href,'https://md.sportsbook.fanduel.com/');
 for(const c of cards){const a=c.links[0];assert.equal(a.href,a.dataset.md);const q=new URL(a.href).searchParams;assert.equal([...q].length,4);}
 assert.equal(app.href,data.app_link);els.tg.click();assert.equal(root.dataset.theme,'dark');
 clock=Date.parse('2026-11-08T09:00:00-05:00');tick();
 for(const c of cards){assert.equal(c.hidden,true);assert.equal(c.links[0].hasAttribute('href'),false);assert.equal(c.links[0].click().prevented,true);}
 buttons[0].click();for(const c of cards)assert.equal(c.links[0].hasAttribute('href'),false);
 assert.equal(els['current-count'].textContent,'0 staged: 0 ready / 0 conditional.');
}
run();run(true);
assert(!source.includes('window.location'));assert(!source.includes('fetch('));
console.log('PASS JS: PA/MD exact two-selection links, generic app untouched, light/dark, storage-denial, expiry/click guard, no auto-launch/network. Real iPhone prefill untested.');
