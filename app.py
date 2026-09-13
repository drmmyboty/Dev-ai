import os, secrets, sqlite3, requests
from functools import wraps
from flask import Flask, request, session, redirect, url_for, render_template, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

APP_NAME = os.getenv('DEV_AI_NAME', 'Dev AI')
MODEL = os.getenv('DEV_AI_MODEL', 'openrouter/free')
API_URL = os.getenv('DEV_AI_API_URL', 'https://openrouter.ai/api/v1/chat/completions')
API_KEY = os.getenv('DEV_AI_API_KEY', '')
DB = os.getenv('DATABASE_URL', 'sqlite:///dev_ai.db')
SECRET = os.getenv('DEV_AI_SECRET', secrets.token_hex(32))

app = Flask(__name__)
app.secret_key = SECRET
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.getenv('DEV_AI_SECURE_COOKIES','1') == '1')

# SQLite keeps this project $0/easy to test. On a host with ephemeral disks, use a persistent DB.
def conn():
    c = sqlite3.connect('dev_ai.db')
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c=conn(); c.executescript('''
      CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS chats(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,title TEXT NOT NULL,created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
      CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT,chat_id INTEGER NOT NULL,role TEXT NOT NULL,content TEXT NOT NULL,created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
    '''); c.commit(); c.close()
init_db()

def csrf():
    if 'csrf' not in session: session['csrf']=secrets.token_urlsafe(24)
    return session['csrf']

def login_required(fn):
    @wraps(fn)
    def wrapper(*a,**kw):
        if not session.get('uid'): return redirect(url_for('login'))
        return fn(*a,**kw)
    return wrapper

def json_login_required(fn):
    @wraps(fn)
    def wrapper(*a,**kw):
        if not session.get('uid'): return jsonify(error='Login required'),401
        return fn(*a,**kw)
    return wrapper

def check_csrf():
    token=request.headers.get('X-CSRF-Token') or request.form.get('csrf') or (request.json or {}).get('csrf')
    return secrets.compare_digest(token or '', csrf())

@app.after_request
def headers(r):
    r.headers['X-Content-Type-Options']='nosniff'; r.headers['X-Frame-Options']='DENY'; r.headers['Referrer-Policy']='same-origin'; r.headers['Content-Security-Policy']="default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'"
    return r

@app.context_processor
def globals(): return {'app_name':APP_NAME,'csrf_token':csrf()}

@app.route('/')
def index():
    return render_template('index.html') if session.get('uid') else redirect(url_for('login'))

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        if not check_csrf(): return 'Bad CSRF',400
        email=request.form.get('email','').strip().lower(); pw=request.form.get('password','')
        c=conn(); u=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone(); c.close()
        if u and check_password_hash(u['password'],pw): session['uid']=u['id']; return redirect('/')
        return render_template('auth.html',mode='login',error='Invalid email or password')
    return render_template('auth.html',mode='login')

@app.route('/signup',methods=['GET','POST'])
def signup():
    if request.method=='POST':
        if not check_csrf(): return 'Bad CSRF',400
        email=request.form.get('email','').strip().lower(); pw=request.form.get('password','')
        if len(pw)<8: return render_template('auth.html',mode='signup',error='Password must be at least 8 characters.')
        try:
            c=conn(); cur=c.execute('INSERT INTO users(email,password) VALUES(?,?)',(email,generate_password_hash(pw))); c.commit(); uid=cur.lastrowid; c.close(); session['uid']=uid; return redirect('/')
        except sqlite3.IntegrityError: return render_template('auth.html',mode='signup',error='Email already registered.')
    return render_template('auth.html',mode='signup')

@app.post('/logout')
def logout():
    if not check_csrf(): return 'Bad CSRF',400
    session.clear(); return redirect(url_for('login'))

@app.post('/change-password')
@login_required
def change_password():
    if not check_csrf(): return jsonify(error='Bad CSRF'),400
    old=request.json.get('old',''); new=request.json.get('new','')
    c=conn(); u=c.execute('SELECT * FROM users WHERE id=?',(session['uid'],)).fetchone()
    if not check_password_hash(u['password'],old): c.close(); return jsonify(error='Current password is wrong'),400
    if len(new)<8: c.close(); return jsonify(error='New password must be 8+ characters'),400
    c.execute('UPDATE users SET password=? WHERE id=?',(generate_password_hash(new),session['uid'])); c.commit(); c.close(); return jsonify(ok=True)

@app.get('/api/chats')
@json_login_required
def chats():
    c=conn(); rows=c.execute('SELECT * FROM chats WHERE user_id=? ORDER BY id DESC',(session['uid'],)).fetchall(); c.close(); return jsonify([dict(r) for r in rows])

@app.post('/api/chats')
@json_login_required
def new_chat():
    if not check_csrf(): return jsonify(error='Bad CSRF'),400
    title=(request.json.get('title') or 'New chat')[:80]
    c=conn(); cur=c.execute('INSERT INTO chats(user_id,title) VALUES(?,?)',(session['uid'],title)); c.commit(); cid=cur.lastrowid; c.close(); return jsonify(id=cid,title=title)

@app.get('/api/chats/<int:cid>')
@json_login_required
def get_chat(cid):
    c=conn(); row=c.execute('SELECT * FROM chats WHERE id=? AND user_id=?',(cid,session['uid'])).fetchone();
    if not row: c.close(); return jsonify(error='Not found'),404
    msgs=[dict(r) for r in c.execute('SELECT role,content FROM messages WHERE chat_id=? ORDER BY id',(cid,)).fetchall()]; c.close(); return jsonify(chat=dict(row),messages=msgs)

@app.post('/api/chat')
@json_login_required
def chat():
    if not check_csrf(): return jsonify(error='Bad CSRF'),400
    data=request.json or {}; cid=int(data.get('chat_id',0)); text=(data.get('message') or '').strip()
    if not text: return jsonify(error='Empty message'),400
    c=conn(); owner=c.execute('SELECT id FROM chats WHERE id=? AND user_id=?',(cid,session['uid'])).fetchone()
    if not owner: c.close(); return jsonify(error='Chat not found'),404
    c.execute('INSERT INTO messages(chat_id,role,content) VALUES(?,?,?)',(cid,'user',text)); hist=c.execute('SELECT role,content FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT 20',(cid,)).fetchall(); c.commit(); c.close()
    if not API_KEY:
        return jsonify(error='AI provider key is not configured. For a $0 deployment, add your own OpenRouter key or another compatible provider key to the server environment.'),503
    messages=[{'role':'system','content':'You are a developer AI assistant. Generate, explain, debug, refactor, convert, and review code. Support many languages including Luau for Roblox. Respect safety limits and never claim code was tested when it was not.'}]
    messages += [{'role':r['role'],'content':r['content']} for r in reversed(hist)]
    try:
        rr=requests.post(API_URL,headers={'Authorization':f'Bearer {API_KEY}','Content-Type':'application/json','HTTP-Referer':request.host_url,'X-Title':APP_NAME},json={'model':MODEL,'messages':messages,'temperature':0.2},timeout=90)
        if rr.status_code>=400: return jsonify(error=f'AI provider error {rr.status_code}: {rr.text[:300]}'),502
        out=rr.json()['choices'][0]['message']['content']
    except Exception as e:
        return jsonify(error=f'AI request failed: {e}'),502
    c=conn(); c.execute('INSERT INTO messages(chat_id,role,content) VALUES(?,?,?)',(cid,'assistant',out)); c.commit(); c.close(); return jsonify(reply=out)

@app.get('/api/branding')
def branding(): return jsonify(name=APP_NAME,model=MODEL)

@app.get('/plugins')
def plugins():
    return jsonify(plugins=[f[:-3] for f in os.listdir('plugins') if f.endswith('.py') and f!='__init__.py'])

if __name__=='__main__':
    app.run(host='0.0.0.0',port=int(os.getenv('PORT','5000')),debug=False)
