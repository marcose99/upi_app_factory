from __future__ import annotations

import importlib
from typing import cast

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

_API_MODULE = 'factory.operator_portal.local_web_api'
_API_VARIABLE = 'app'
_PORTAL_HTML = '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1">\n<title>UPI App Factory — Operator Portal</title>\n<style>\n:root{color-scheme:dark;--bg:#08111f;--panel:#101d31;--line:#263b59;--text:#eef5ff;--muted:#9fb2cc;--ok:#5ee1a2;--warn:#ffc86b;--accent:#7eb6ff}\n*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 15% 0,#18365d 0,#08111f 42%);font:15px/1.5 system-ui,sans-serif;color:var(--text)}\nheader{padding:28px clamp(20px,4vw,60px);border-bottom:1px solid var(--line);background:#08111fdd;position:sticky;top:0;backdrop-filter:blur(14px);z-index:5}\nh1{margin:0;font-size:clamp(26px,4vw,46px)}.sub{color:var(--muted);max-width:880px}.badges{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}\n.badge{padding:6px 10px;border:1px solid var(--line);border-radius:999px;background:#10243d}.ok{color:var(--ok)}\nmain{padding:28px clamp(20px,4vw,60px) 60px;display:grid;gap:18px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px}\n.card{background:linear-gradient(145deg,#12223a,#0d192a);border:1px solid var(--line);border-radius:18px;padding:20px;box-shadow:0 18px 45px #0005;animation:rise .45s ease both}\n@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}h2{margin-top:0;font-size:18px}\nbutton,input,select,textarea{width:100%;border:1px solid var(--line);border-radius:10px;background:#081424;color:var(--text);padding:10px;margin-top:8px}\nbutton{cursor:pointer;background:#17365d;font-weight:700}button:hover{filter:brightness(1.18)}textarea{min-height:130px;font-family:ui-monospace,monospace}\npre{white-space:pre-wrap;overflow:auto;background:#07101d;border-radius:12px;padding:14px;min-height:90px;color:#cfe2ff}\n.route{padding:8px 0;border-bottom:1px solid #ffffff12}.method{display:inline-block;width:58px;color:var(--accent);font-weight:800}\na{color:var(--accent)}footer{color:var(--muted);padding-top:12px}\n</style>\n</head>\n<body>\n<header>\n<h1>UPI App Factory</h1>\n<p class="sub">Governed operator control plane for requirements intake, application engineering, validation, evidence inspection and verified handoff.</p>\n<div class="badges">\n<span class="badge ok">Mock-safe local</span><span class="badge">Real payment calls disabled</span>\n<span class="badge">Human-gated engineering</span><span class="badge">Certification-ready-not-certified</span>\n</div>\n</header>\n<main>\n<div class="grid">\n<section class="card"><h2>Control-plane status</h2><button onclick="refresh()">Refresh portal</button><pre id="status">Loading…</pre></section>\n<section class="card"><h2>Download & evidence centre</h2><div id="downloads">Discovering routes…</div></section>\n<section class="card"><h2>Requirements intake</h2><textarea id="requirements"># UPI application requirements\nDescribe the payment capability, business rules, governance constraints, mock boundaries and acceptance scenarios.</textarea><p class="sub">Use the discovered run/intake API below. Protected execution remains human-gated.</p></section>\n</div>\n<div class="grid">\n<section class="card"><h2>API explorer</h2><div id="routes">Loading OpenAPI…</div></section>\n<section class="card"><h2>Governed request console</h2>\n<select id="method"><option>GET</option><option>POST</option><option>PUT</option><option>DELETE</option></select>\n<input id="path" value="/operator-portal/health">\n<textarea id="body">{}</textarea><button onclick="invoke()">Invoke selected endpoint</button>\n<pre id="response"></pre></section>\n</div>\n<footer>All operations are local-first. External payment systems remain mocked. Evidence and release actions remain governed.</footer>\n</main>\n<script>\nlet spec={};\nasync function refresh(){\n  const s=document.getElementById(\'status\');\n  try{\n    const [health,openapi]=await Promise.all([fetch(\'/operator-portal/health\'),fetch(\'/openapi.json\')]);\n    const h=await health.json(); spec=await openapi.json();\n    s.textContent=JSON.stringify({health:h,title:spec.info?.title,path_count:Object.keys(spec.paths||{}).length},null,2);\n    renderRoutes();\n  }catch(e){s.textContent=String(e)}\n}\nfunction renderRoutes(){\n const paths=spec.paths||{}, routes=document.getElementById(\'routes\'), downloads=document.getElementById(\'downloads\');\n routes.innerHTML=\'\'; downloads.innerHTML=\'\';\n Object.entries(paths).forEach(([p,ops])=>Object.keys(ops).forEach(m=>{\n   if(![\'get\',\'post\',\'put\',\'delete\',\'patch\'].includes(m))return;\n   const d=document.createElement(\'div\');d.className=\'route\';d.innerHTML=`<span class="method">${m.toUpperCase()}</span><a href="#" data-p="${p}" data-m="${m}">${p}</a>`;\n   d.querySelector(\'a\').onclick=(e)=>{e.preventDefault();document.getElementById(\'path\').value=p;document.getElementById(\'method\').value=m.toUpperCase()};\n   routes.appendChild(d);\n   if(/download|export|bundle|artifact|evidence/i.test(p)){const a=document.createElement(\'div\');a.className=\'route\';a.textContent=`${m.toUpperCase()} ${p}`;downloads.appendChild(a)}\n }));\n if(!downloads.children.length)downloads.textContent=\'No public download route was advertised.\';\n}\nasync function invoke(){\n const method=document.getElementById(\'method\').value,path=document.getElementById(\'path\').value,out=document.getElementById(\'response\');\n const options={method,headers:{\'Content-Type\':\'application/json\'}};\n if(![\'GET\',\'DELETE\'].includes(method))options.body=document.getElementById(\'body\').value;\n try{const r=await fetch(path,options);const t=await r.text();out.textContent=`HTTP ${r.status}\\n${t}`}catch(e){out.textContent=String(e)}\n}\nrefresh();\n</script>\n</body>\n</html>'

_module = importlib.import_module(_API_MODULE)
_api_app = cast(FastAPI, getattr(_module, _API_VARIABLE))

app = FastAPI(
    title="UPI App Factory Operator Portal",
    description=(
        "Local-first governed control plane with mock-safe application "
        "engineering, evidence and download capabilities."
    ),
    version="1.0.0-rc",
)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
@app.get(
    "/operator-portal",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def operator_portal_ui() -> HTMLResponse:
    return HTMLResponse(_PORTAL_HTML)


@app.get("/operator-portal/health")
def operator_portal_health() -> dict[str, object]:
    return {
        "status": "ok",
        "mode": "mock-safe-local",
        "real_payment_calls": "disabled",
        "llm_calls": 0,
    }


app.include_router(_api_app.router)
