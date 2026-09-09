from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from scripts.cloud_shell_channels import browser_channels_script
from scripts.cloud_shell_proxy import browser_transport_script

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Browser shim tests require the Node runtime")
PREFIX = "/session/proxy/5000/"


def run_browser_script(script: bytes, harness: str, **values):
    source = script.decode().split(">", 1)[1].rsplit("</script>", 1)[0]
    completed = subprocess.run(
        [NODE, "-e", harness],
        input=json.dumps({"script": source, **values}),
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_status_shim_restores_core_and_lab_api_success_and_errors() -> None:
    harness = r"""
const fs = require('node:fs'), vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
global.window = globalThis;
global.location = {href:'https://preview.example.test/session/proxy/5000/lab',
  origin:'https://preview.example.test'};
let status, marked, preserved;
global.fetch = async (request, options) => {
  marked = options.headers.get('X-Foundry-Cloud-Shell') === '1';
  preserved = options.headers.get('X-Test') === 'preserved';
  return new Response(JSON.stringify(marked ? {__foundry_relay:1, status,
    headers:{'Content-Type':'application/json'}, body:status===204?'':'{"error":"synthetic"}'}
    : {plain:true}), {status:200});
};
vm.runInThisContext(input.script);
(async()=>{
  const results=[];
  for(const route of ['api', 'api/sessions',
    'lab/api/settings/@jupyterlab/apputils-extension:themes', 'lab/api/workspaces/default']){
    for(status of [204,403,404]){
      const response=await fetch('https://preview.example.test/session/proxy/5000/'+route,
        {method:'PUT',headers:{'X-Test':'preserved'}});
      results.push({route, expected:status, status:response.status, marked, preserved,
        body:await response.text()});
    }
  }
  for(const url of [
    'https://other.example.test/session/proxy/5000/api/sessions',
    'https://preview.example.test/session/proxy/5000/lab/api/settings-other',
    'https://preview.example.test/other/api/sessions']){
    const response=await fetch(url,{headers:new Headers({'X-Test':'preserved'})});
    results.push({url,status:response.status,marked,preserved});
  }
  console.log(JSON.stringify(results));
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    results = run_browser_script(browser_transport_script(PREFIX), harness)
    for row in results[:12]:
        assert row["marked"] and row["preserved"]
        assert row["status"] == row["expected"]
        assert row["body"] == ("" if row["expected"] == 204 else '{"error":"synthetic"}')
    for row in results[12:]:
        assert not row["marked"]
        assert row["status"] == 200


@pytest.mark.parametrize("mode", ["binary", "close-error", "reader-error"])
def test_browser_channel_binary_delivery_and_visible_failures(mode: str) -> None:
    harness = r"""
const fs=require('node:fs'), vm=require('node:vm');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
global.window=globalThis;
global.location={href:'https://preview.example.test/session/proxy/5000/lab',
  origin:'https://preview.example.test',host:'preview.example.test'};
global.document={cookie:'_xsrf=synthetic-xsrf'};
global.CloseEvent=class extends Event{
  constructor(type,options){super(type);Object.assign(this,options);}
};
global.WebSocket=class {constructor(url){this.url=String(url);this.native=true;}};
const warnings=[], requests=[], sent=[];
console.warn=message=>warnings.push(message);
let releasePoll, polls=0;
const response=data=>new Response(JSON.stringify(data),{status:200});
global.fetch=async(url,options)=>{
  requests.push({method:options.method,xsrf:options.headers['X-XSRFToken'],
    credentials:options.credentials});
  if(options.method==='POST' && url.endsWith('/channels'))
    return response({ok:true,id:'a'.repeat(32)});
  if(options.method==='POST'){
    sent.push(JSON.parse(options.body));return response({ok:true});
  }
  if(options.method==='DELETE')
    return response({ok:input.mode!=='close-error'});
  if(polls++===0)return new Promise(resolve=>{releasePoll=resolve;});
  return response({ok:true,messages:[
    {type:'binary',data:Buffer.from([0,255,4]).toString('base64')},
    {type:'text',data:'execution-complete'}],closed:true,close_code:1000});
};
vm.runInThisContext(input.script);
(async()=>{
  const other=new WebSocket('wss://other.example.test/api/kernels/other/channels');
  const socket=new WebSocket('wss://preview.example.test/session/proxy/5000/api/kernels/'
    +'11111111-1111-4111-8111-111111111111/channels?session_id='
    +'22222222-2222-4222-8222-222222222222');
  const messages=[];
  let errors=0;
  socket.addEventListener('message',event=>messages.push(
    event.data instanceof ArrayBuffer?Array.from(new Uint8Array(event.data)):event.data));
  socket.addEventListener('error',()=>errors++);
  const closed=new Promise(resolve=>socket.addEventListener('close',resolve));
  await new Promise(resolve=>socket.addEventListener('open',resolve));
  if(input.mode==='binary'){
    socket.send(new Uint8Array([9,0,255,4,8]).subarray(1,4));
    await socket._sendQueue;
    releasePoll(response({ok:true,messages:Array.from({length:64},(_,i)=>(
      {type:'text',data:String(i)})),closed:false,close_code:1000}));
  }else if(input.mode==='reader-error'){
    releasePoll(response({ok:true,messages:[{type:'text',data:'before failure'}],
      closed:true,close_code:1006}));
  }else{
    socket.close();
  }
  const event=await closed;
  console.log(JSON.stringify({native:other.native,messages,sent,warnings,errors,
    code:event.code,wasClean:event.wasClean,requests}));
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    result = run_browser_script(browser_channels_script(PREFIX), harness, mode=mode)
    assert result["native"]
    assert all(
        request["xsrf"] == "synthetic-xsrf" and request["credentials"] == "same-origin"
        for request in result["requests"]
    )
    if mode == "binary":
        assert result["sent"] == [{"type": "binary", "data": "AP8E"}]
        assert len(result["messages"]) == 66
        assert result["messages"][-2:] == [[0, 255, 4], "execution-complete"]
        assert result["code"] == 1000 and result["wasClean"]
        assert result["errors"] == 0
    else:
        assert result["code"] == 1006 and not result["wasClean"]
        assert result["errors"] == 1
        if mode == "close-error":
            assert len(result["warnings"]) == 1
            assert "cleanup failed" in result["warnings"][0]
        else:
            assert result["messages"] == ["before failure"]
