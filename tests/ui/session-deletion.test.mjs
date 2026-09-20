import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {RuntimeAdapter} from '../../apps/ui/runtime-adapter.js';
import {SessionDeletion,sessionDeletionConfirmation} from '../../apps/ui/session-deletion.js';

const row={session_id:'session-test',song_name:'Temporary song'};
const state=(id=row.session_id)=>({session_id:id,state_version:1,event_sequence:1,workflow_policy:'live_reference_v1',capture:{source_generation:1}});
const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};};
const adapter=options=>new RuntimeAdapter({onSnapshot(){},onStatus(){},...options});

test('confirmation identifies session, irreversible history, active stop and retained assets',()=>{
 const copy=sessionDeletionConfirmation(row);
 for(const text of [row.song_name,'listening','stop','permanently deleted','song and uploaded reference will stay available'])assert.ok(copy.includes(text));
 assert.equal(copy.includes(row.session_id),false,'internal session IDs stay out of normal confirmation copy');
});

test('cancel and offline examples never delete or remove recent entries',async()=>{
 const flow=new SessionDeletion(),a={deleteSession(){assert.fail('not authorized');}},remove=()=>assert.fail('recent entry must remain');
 assert.equal((await flow.request(row,{adapter:a,authoritative:true,confirm:()=>false,onDeleted:remove})).cancelled,true);
 assert.equal((await flow.request(row,{adapter:a,authoritative:false,confirm:()=>assert.fail('offline confirmation'),onDeleted:remove})).blocked,true);
 assert.equal(flow.pending.size,0);
});

test('confirmation/pending duplicate guard and removal only after success',async()=>{
 const flow=new SessionDeletion(),confirmation=deferred(),ack=deferred(),removed=[];let requests=0;
 const options={adapter:{deleteSession(){requests++;return ack.promise;}},authoritative:true,confirm:()=>confirmation.promise,onDeleted:id=>removed.push(id)};
 const first=flow.request(row,options);assert.equal((await flow.request(row,options)).pending,true);
 confirmation.resolve(true);await Promise.resolve();assert.equal(requests,1);assert.deepEqual(removed,[]);
 assert.equal((await flow.request(row,options)).pending,true);
 ack.resolve({session_id:row.session_id,deleted:true});await first;
 assert.deepEqual(removed,[row.session_id]);assert.equal(flow.pending.size,0);
});

test('failed deletion retains recent entry and allows explicit retry',async()=>{
 const flow=new SessionDeletion();let calls=0,removed=0;
 const options={adapter:{async deleteSession(){if(++calls===1)throw Error('offline');return {session_id:row.session_id,deleted:true};}},authoritative:true,confirm:()=>true,onDeleted:()=>removed++};
 await assert.rejects(flow.request(row,options),/offline/);assert.equal(removed,0);assert.equal(flow.pending.size,0);
 await flow.request(row,options);assert.equal(removed,1);
});

test('adapter uses bodyless DELETE, guards duplicate and fences active late requests',async()=>{
 const notifications=[],a=adapter({onSnapshot:s=>notifications.push(s)}),s=state(),ack=deferred(),late=deferred(),requests=[];
 a.activateSession(s.session_id);a.acceptSnapshot(s);
 let closed=0;a.socket={close(){closed++;}};a.probe={session_id:s.session_id};
 a.request=(path,options)=>{requests.push([path,options]);return options?.method==='DELETE'?ack.promise:late.promise;};
 const refreshing=a.refresh(s.session_id),deleting=a.deleteSession(s.session_id);
 assert.equal(a.deleteSession(s.session_id),deleting);assert.equal(a.snapshot,s);
 ack.resolve({session_id:s.session_id,deleted:true});await deleting;
 assert.deepEqual(requests[1],[`/sessions/${s.session_id}`,{method:'DELETE'}]);
 assert.equal(closed,1);assert.equal(a.activeSessionId,null);assert.equal(a.snapshot,null);assert.equal(a.probe,null);assert.equal(a.cursor,0);assert.equal(a.stopped,true);assert.equal(a.reconnectTimer,null);
 late.resolve({...s,state_version:999,event_sequence:999});assert.equal(await refreshing,null);
 assert.equal(a.acceptSnapshot(s),false);assert.throws(()=>a.activateSession(s.session_id),/deleted/);assert.equal(notifications.length,1);
 await a.recover(s.session_id);assert.equal(requests.length,2);
});

test('failed or malformed acknowledgement does not clear bindings or record deletion',async()=>{
 for(const failure of [Error('offline'),{session_id:'other',deleted:true},{session_id:row.session_id,deleted:false}]){
  const a=adapter(),s=state();a.activateSession(s.session_id);a.acceptSnapshot(s);
  a.request=async()=>{if(failure instanceof Error)throw failure;return failure;};
  await assert.rejects(a.deleteSession(s.session_id));assert.equal(a.snapshot,s);assert.equal(a.activeSessionId,s.session_id);assert.equal(a.deletedSessionIds.size,0);assert.equal(a.pendingDeletes.size,0);
 }
});

test('deletion completing after switching sessions does not clear the new session',async()=>{
 const a=adapter(),ack=deferred(),s=state();a.activateSession(s.session_id);a.acceptSnapshot(s);a.request=()=>ack.promise;
 const deleting=a.deleteSession(s.session_id);a.activateSession('other-session');const other=state('other-session');a.acceptSnapshot(other);
 const generation=a.generation;let closed=0;a.socket={close(){closed++;}};
 ack.resolve({session_id:s.session_id,deleted:true});await deleting;
 assert.equal(a.snapshot,other);assert.equal(a.activeSessionId,other.session_id);assert.equal(a.generation,generation);assert.equal(closed,0);assert.equal(a.stopped,false);
});

test('4404 is terminal and fences late socket events without acknowledging deletion',async()=>{
 const originalSocket=globalThis.WebSocket,originalLocation=globalThis.location,sockets=[],unavailable=[],seen=[];
 globalThis.location={protocol:'http:',host:'localhost'};globalThis.WebSocket=class{constructor(){sockets.push(this);}close(){}};
 try{
  const a=adapter({onSessionUnavailable:id=>unavailable.push(id),onSnapshot:s=>seen.push(s)}),s=state();
  a.activateSession(s.session_id);a.acceptSnapshot(s);a.connect(s.session_id,1);const old=sockets[0];
  old.onclose({code:4404});assert.deepEqual(unavailable,[s.session_id]);assert.equal(a.snapshot,null);assert.equal(a.activeSessionId,null);assert.equal(a.stopped,true);assert.equal(a.reconnectTimer,null);
  assert.equal(a.deletedSessionIds.size,0,'catalog removal still requires DELETE ack');
  old.onmessage({data:'obsolete invalid JSON'});old.onerror();await a.recover(s.session_id);assert.equal(sockets.length,1);assert.equal(seen.length,1);
  a.activateSession('other');a.acceptSnapshot(state('other'));old.onclose({code:4404});assert.equal(a.activeSessionId,'other');assert.equal(unavailable.length,1);a.stopEvents();
 }finally{globalThis.WebSocket=originalSocket;globalThis.location=originalLocation;}
});

test('delayed open cannot reconnect a deleted session',async()=>{
 const a=adapter(),late=deferred(),s=state();a.request=async(path,options)=>options?.method==='DELETE'?{session_id:s.session_id,deleted:true}:late.promise;
 a.connect=()=>assert.fail('deleted open must not reconnect');const opening=a.openSession(s.session_id);
 await a.deleteSession(s.session_id);late.resolve(s);await assert.rejects(opening,/changed/);assert.equal(a.snapshot,null);
});

test('recent entry and active session expose an explicit styled delete action and guard catalog resurrection',()=>{
 const source=readFileSync(new URL('../../apps/ui/app.js',import.meta.url),'utf8');
 assert.match(source,/catalog\.forEach\(x=>list\.append\(recentSessionRow\(x\)\)\)/);
 assert.match(source,/confirm:confirmSessionDeletion/);assert.match(source,/'delete-session'/);
 assert.match(source,/typeof dialog\.showModal==='function'/);assert.match(source,/'danger-action'/);
 assert.match(source,/snapshot\.session_id,song_name:snapshot\.song\.name/);
 assert.match(source,/dialog\.addEventListener\('cancel',event=>\{event\.preventDefault\(\);finish\(false\);\}\)/);
 assert.match(source,/aria-labelledby/);assert.match(source,/aria-describedby/);
 assert.match(source,/onDeleted:id=>\{removeCatalog\(id\);clearSessionView\(id\);\}/);
 assert.match(source,/function saveCatalog\(s\).*deletedSessionIds\.has\(s.session_id\)/);
 assert.match(source,/function loadSession\(id\).*activeSessionId!==sessionId/);
});
