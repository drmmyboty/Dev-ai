let chatId=null;
const $=s=>document.querySelector(s);
async function api(url,opt={}){opt.headers={...(opt.headers||{}),'Content-Type':'application/json','X-CSRF-Token':window.CSRF};const r=await fetch(url,opt);return r.json();}
function add(role,text){let d=document.createElement('div');d.className='msg '+role;d.textContent=text;$('#messages').appendChild(d);$('#messages').scrollTop=1e9;}
async function loadChats(){let a=await api('/api/chats');$('#chats').innerHTML='';a.forEach(c=>{let b=document.createElement('button');b.textContent=c.title;b.onclick=()=>loadChat(c.id);$('#chats').appendChild(b)});}
async function loadChat(id){chatId=id;let x=await api('/api/chats/'+id);$('#messages').innerHTML='';x.messages.forEach(m=>add(m.role,m.content));}
$('#new').onclick=async()=>{let x=await api('/api/chats',{method:'POST',body:JSON.stringify({title:'New chat'})});await loadChats();await loadChat(x.id)};
$('#send').onclick=async()=>{let t=$('#input').value.trim();if(!t)return;if(!chatId){let x=await api('/api/chats',{method:'POST',body:JSON.stringify({title:t.slice(0,50)})});chatId=x.id;await loadChats()}$('#input').value='';add('user',t);$('#send').disabled=true;let x=await api('/api/chat',{method:'POST',body:JSON.stringify({chat_id:chatId,message:t})});add('assistant',x.reply||x.error||'No response');$('#send').disabled=false};
$('#cp').onclick=async()=>{let x=await api('/change-password',{method:'POST',body:JSON.stringify({old:$('#old').value,new:$('#nw').value})});$('#cpm').textContent=x.ok?'Changed':x.error||'Error'};
loadChats();
