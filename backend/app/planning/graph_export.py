"""Safe standalone human graph viewer. It performs no network or model requests."""

import json

from .graph import project_graph


def graph_files(plan, ledger, *, state="approved", worker_limits=None) -> dict[str, str]:
    graph = project_graph(plan, ledger, state=state, worker_limits=worker_limits)
    encoded = json.dumps(graph, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    embedded = (encoded.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
                .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    files = {
        "graph/graph.json": encoded,
        "graph/index.html": _VIEWER.replace("__GRAPH_DATA__", embedded),
    }
    for node in graph["nodes"]:
        # IDs come from canonical indexes, never model-authored names or paths.
        files[f"graph/nodes/{node['id']}.json"] = (
            json.dumps(node, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
        )
    return files


_VIEWER = r'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline';
style-src 'unsafe-inline'; img-src 'none'; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>Intent · complete plan graph</title>
<style>
:root{color-scheme:light;font:16px/1.5 system-ui,sans-serif;color:#18302c;background:#f7f8f4}
*{box-sizing:border-box}body{margin:0}header{padding:1.5rem 2rem;border-bottom:1px solid #b9c9c0}
h1{font-size:1.6rem;margin:0}h2{font-size:1.1rem}p{margin:.5rem 0}#identity{overflow-wrap:anywhere}
button,input,select{font:inherit;border:1px solid #8aa499;border-radius:.35rem;padding:.4rem .65rem;
background:white;color:#18302c}button{cursor:pointer}button:hover,button[aria-pressed=true]{background:#deeee3}
:focus-visible{outline:3px solid #a84c18;outline-offset:3px}
label{display:inline-flex;gap:.5rem;align-items:center}
.controls{display:flex;flex-wrap:wrap;gap:.65rem;padding:1rem 2rem}
main{display:grid;grid-template-columns:1fr 24rem;gap:1rem;padding:0 2rem 2rem}
.canvas{border:1px solid #b9c9c0;background:#fff;border-radius:.5rem;overflow:hidden}
svg{width:100%;height:36rem;display:block;touch-action:none}svg text{font:13px system-ui;pointer-events:none}
svg g{cursor:pointer}svg g:focus circle{stroke:#a84c18;stroke-width:5}#inspector{min-width:0}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eaf0e9;padding:.8rem;font:12px/1.6 monospace;
max-height:38rem;overflow:auto}#outline{padding-left:1.5rem;max-height:18rem;overflow:auto}
#outline li{margin:.5rem 0}#outline button{margin-right:.4rem}small{color:#405b52}
@media(max-width:850px){main{grid-template-columns:1fr;padding:0 1rem 1rem}.controls,header{padding:1rem}
svg{height:28rem}pre{max-height:26rem}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
</style>
<header><h1>Intent · complete project plan</h1><p id="identity"></p>
<p>This human overview includes every branch. Worker inputs use a separate scoped bundle.</p></header>
<nav class="controls" aria-label="Graph controls">
<label>Search plan <input id="search" type="search" placeholder="Scope, source, acceptance…"></label>
<label>Node type <select id="type"><option value="">All types</option>
<option>root</option><option>phase</option>
<option>package</option><option>task</option><option>screen</option></select></label>
<label>Detail state <select id="status"><option value="">All detail states</option>
<option>validated</option><option>pending</option></select></label>
<button id="center">Center root</button><button id="fit">Fit graph</button>
<button id="zoomIn" aria-label="Zoom in">+</button><button id="zoomOut" aria-label="Zoom out">−</button>
<button id="expand">Expand all</button><span id="count" role="status"></span></nav>
<main><section><div class="canvas"><svg id="canvas" role="group" aria-label="Complete plan graph"
viewBox="-800 -550 1600 1100"></svg></div>
<p><small>Solid lines contain work; dashed arrows point to prerequisites. Screen attachments share the root.
Drag the canvas to pan. All details are also accessible through the buttons below.</small></p>
<h2>Keyboard outline</h2><ol id="outline" aria-label="Plan nodes"></ol></section>
<aside id="inspector" aria-live="polite"><p id="breadcrumb"></p><h2 id="title"></h2><p id="nodeState"></p>
<pre id="body" tabindex="0" aria-label="Complete selected node details"></pre>
<details><summary>Source paths, citations and edge provenance</summary><pre id="provenance"></pre></details>
</aside></main>
<script id="graph" type="application/json">__GRAPH_DATA__</script>
<script>
'use strict';
const graph=JSON.parse(document.getElementById('graph').textContent);
const byId=new Map(graph.nodes.map(n=>[n.id,n]));
const get=id=>document.getElementById(id);
const svg=get('canvas'), ns='http://www.w3.org/2000/svg';
const collapsed=new Set();let selected=graph.root_id, box=[-800,-550,1600,1100], drag=null;
const positions=new Map([[graph.root_id,[0,0]]]);
const phases=graph.nodes.filter(n=>n.kind==='phase');
const polar=(angle,radius)=>[Math.cos(angle)*radius,Math.sin(angle)*radius];
phases.forEach((phase,i)=>{
 const angle=-Math.PI/2+i*2*Math.PI/Math.max(1,phases.length);
 positions.set(phase.id,polar(angle,270));
 const children=graph.nodes.filter(n=>n.parent_id===phase.id);
 children.forEach((p,j)=>{
  const pa=angle+(j-(children.length-1)/2)*.42;positions.set(p.id,polar(pa,480));
  const tasks=graph.nodes.filter(n=>n.parent_id===p.id);
  tasks.forEach((t,k)=>positions.set(t.id,polar(pa+(k-(tasks.length-1)/2)*.17,690)));
 });
});
graph.nodes.filter(n=>n.kind==='screen').forEach((n,i)=>positions.set(n.id,polar(Math.PI/4+i*.45,200)));
const source=graph.source;
get('identity').textContent=(source.mode==='demo'?'DEMO · synthetic plan':'Live plan')+' · '+source.plan_id+
' · revision '+source.revision+' · requirements '+source.requirements_revision+' · '+graph.state+
' · SHA-256 '+source.content_hash+(graph.partial?' · PARTIAL, not approvable':'');
function element(tag,attrs,text){const el=document.createElementNS(ns,tag);
 for(const [key,value] of Object.entries(attrs||{}))el.setAttribute(key,String(value));
 if(text!==undefined)el.textContent=text;return el;}
function ancestry(node){const chain=[];let current=node;
 while(current){chain.unshift(current);current=byId.get(current.parent_id);}return chain;}
function visibleNodes(){const query=get('search').value.toLocaleLowerCase(), type=get('type').value;
 const status=get('status').value;const matches=graph.nodes.filter(n=>
 (!type||n.kind===type)&&(!status||n.status===status)&&
 (!query||JSON.stringify(n).toLocaleLowerCase().includes(query)));
 const result=new Set([graph.root_id]);
 matches.forEach(n=>{const chain=ancestry(n);
 if(query||!chain.slice(0,-1).some(p=>collapsed.has(p.id)))chain.forEach(p=>result.add(p.id));});
 return graph.nodes.filter(n=>result.has(n.id));}
function select(id){selected=id;const n=byId.get(id);if(!n)return;
 get('breadcrumb').textContent=ancestry(n).map(p=>p.id).join(' → ');
 get('title').textContent=n.title;
 get('nodeState').textContent=n.kind+' · '+n.status+
 ' · Node validation is distinct from execution evidence and human acceptance.';
 get('body').textContent=JSON.stringify(n.body,null,2);
 get('provenance').textContent=JSON.stringify({citations:n.citations,source_paths:n.source_paths,
 edges:graph.edges.filter(e=>e.source===id||e.target===id)},null,2);draw();}
function draw(){svg.replaceChildren();const visible=visibleNodes(), ids=new Set(visible.map(n=>n.id));
 const defs=element('defs');const marker=element('marker',{id:'arrow',viewBox:'0 0 10 10',refX:9,
 refY:5,markerWidth:6,markerHeight:6,orient:'auto-start-reverse'});
 marker.append(element('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#a65a30'}));
 defs.append(marker);svg.append(defs);
 graph.edges.filter(e=>ids.has(e.source)&&ids.has(e.target)).forEach(e=>{
  const a=positions.get(e.source),b=positions.get(e.target);
  const line=element('line',{x1:a[0],y1:a[1],x2:b[0],y2:b[1],stroke:e.type==='depends_on'?'#a65a30':'#91afa0',
  'stroke-width':e.type==='contains'?2:1.5,'stroke-dasharray':e.type==='depends_on'?'7 6':'none'});
  if(e.type==='depends_on')line.setAttribute('marker-end','url(#arrow)');
  line.append(element('title',{},e.type+': '+e.source+' → '+e.target+' ('+e.provenance+')'));svg.append(line);
 });
 visible.forEach(n=>{const point=positions.get(n.id), radius=n.kind==='root'?65:36;
  const group=element('g',{transform:'translate('+point[0]+' '+point[1]+')',tabindex:0,role:'button',
  'aria-label':n.kind+' '+n.id+': '+n.title,'aria-pressed':selected===n.id});
  group.append(element('circle',{r:radius,fill:n.id===selected?'#1c5f4c':n.status==='pending'?'#fff4e4':'#e3efe6',
  stroke:n.id===selected?'#113e32':'#527b68','stroke-width':n.kind==='root'?3:2}));
  group.append(element('text',{'text-anchor':'middle',y:4,fill:n.id===selected?'white':'#18302c'},
  n.kind==='root'?'PROJECT':n.id));
  group.append(element('text',{'text-anchor':'middle',y:radius+22,fill:'#18302c'},
  n.title.length>36?n.title.slice(0,33)+'…':n.title));
  group.addEventListener('click',()=>select(n.id));group.addEventListener('keydown',event=>{
   if(event.key==='Enter'||event.key===' '){event.preventDefault();select(n.id);}});svg.append(group);
 });
 svg.setAttribute('viewBox',box.join(' '));get('count').textContent=visible.length+'/'+graph.nodes.length+
 ' nodes visible · '+collapsed.size+' branches collapsed';
 const outline=get('outline');outline.replaceChildren();visible.forEach(n=>{
  const li=document.createElement('li'), button=document.createElement('button');
  button.textContent=n.id+' · '+n.title;button.setAttribute('aria-pressed',String(n.id===selected));
  button.addEventListener('click',()=>select(n.id));li.append(button);
  if(graph.nodes.some(child=>child.parent_id===n.id)){
   const toggle=document.createElement('button');toggle.textContent=collapsed.has(n.id)?'Expand':'Collapse';
   toggle.setAttribute('aria-expanded',String(!collapsed.has(n.id)));
   toggle.setAttribute('aria-label',toggle.textContent+' '+n.id);
   toggle.addEventListener('click',()=>{collapsed.has(n.id)?collapsed.delete(n.id):collapsed.add(n.id);draw();});
   li.append(toggle);
  }outline.append(li);
 });}
function zoom(factor){const cx=box[0]+box[2]/2,cy=box[1]+box[3]/2;
 const width=Math.max(400,Math.min(4000,box[2]*factor));
 box=[cx-width/2,cy-width*.6875/2,width,width*.6875];draw();}
get('center').addEventListener('click',()=>{box=[-800,-550,1600,1100];draw();});
get('fit').addEventListener('click',()=>{box=[-850,-800,1700,1600];draw();});
get('zoomIn').addEventListener('click',()=>zoom(.8));get('zoomOut').addEventListener('click',()=>zoom(1.25));
get('expand').addEventListener('click',()=>{collapsed.clear();draw();});
['search','type','status'].forEach(id=>get(id).addEventListener('input',draw));
svg.addEventListener('pointerdown',event=>{if(event.target.closest('g'))return;
 drag={x:event.clientX,y:event.clientY,box:[...box]};svg.setPointerCapture(event.pointerId);});
svg.addEventListener('pointermove',event=>{if(!drag)return;const rect=svg.getBoundingClientRect();
 box=[drag.box[0]-(event.clientX-drag.x)*drag.box[2]/rect.width,
 drag.box[1]-(event.clientY-drag.y)*drag.box[3]/rect.height,drag.box[2],drag.box[3]];
 svg.setAttribute('viewBox',box.join(' '));});
svg.addEventListener('pointerup',()=>{drag=null;});svg.addEventListener('pointercancel',()=>{drag=null;});
select(graph.root_id);
</script></html>'''
