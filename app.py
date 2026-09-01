import os
import random
import string
import requests
import psycopg2
import eventlet
from flask import Flask, render_template, request, jsonify, Response
from flask_socketio import SocketIO, emit, join_room, leave_room
from dotenv import load_dotenv 

load_dotenv()

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS leaderboard (
                id SERIAL PRIMARY KEY,
                player_name TEXT NOT NULL,
                score INTEGER NOT NULL,
                lang_mode TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print("Veritabani baglanti hatasi:", e)

init_db()


TR_HITS = [
    "Duman", "Mor ve Otesi", "maNga", "Sebnem Ferah", "Teoman", "Ayna", "Yalin", "MFO", "Onur Ozdemir",
    "Sakin", "Vega", "Athena", "Dedublüman","Can Bonomo", "emre aydin",      
    "Model", "Hayko Cepkin", "Tarkan", "Sertab Erener", "Kenan Dogulu", "Ozlem Tekin",
    "Levent Yuksel","Nazan Öncel", "Göksel", "Pinhani", "Baris Manco", "Cem Karaca", "Cilekes", "Redd" 
]

EN_HITS = [
    "Nirvana", "Jeff Buckley", "Red Hot Chili Peppers", "Queen", "David Guetta", "Lady Gaga", "Metallica", "Michael Jackson",
    "Eminem", "Kanye West", "Timbaland", "Black Eyed Peas", "Bon Jovi", "Marilyn Manson", "Britney Spears", "Pink Floyd",
    "One Direction", "Arctic Monkeys", "Bruno Mars", "Rihanna", "Flo Rida", "Daft Punk",
    "Madonna", "Modern Talking", "Twenty One Pilots", "Radiohead", "Sting", "Scorpions" 
]

EXCLUDED_TR_TITLES = [
    "love me back", "we could be the same", "everyway that i can", 
    "for real", "shake it up", "always", "feel your love",
    "nick the chopper", "runaway", "little darling", "lady of the seventh sky"
]

EXCLUDED_EN_TITLES = [
    "remix", "live", "karaoke", "instrumental", "cover", "spanish version", "acoustic", "girl like me"
]

def fetch_itunes_tracks(artist_list, limit=5):
    tracks = []
    shuffled_artists = random.sample(artist_list, len(artist_list))
    for artist in shuffled_artists:
        if len(tracks) >= limit:
            break
        try:
            is_tr = artist in TR_HITS
            country_code = "tr" if is_tr else "us"
            url = f"https://itunes.apple.com/search?term={requests.utils.quote(artist)}&country={country_code}&entity=song&attribute=artistTerm&limit=30"
            res = requests.get(url, timeout=4).json()
            
            results = []
            for r in res.get('results', []):
                if r.get('previewUrl') and r.get('trackName'):
                    raw_name_test = r['trackName'].lower()
                    if is_tr and any(ex in raw_name_test for ex in EXCLUDED_TR_TITLES):
                        continue
                        
                    if not is_tr and any(ex in raw_name_test for ex in EXCLUDED_EN_TITLES):
                        continue
                        
                    art_clean = artist.lower().replace("ö", "o").replace("ü", "u").replace("ş", "s").replace("ç", "c").replace("ğ", "g").replace("ı", "i")
                    res_art_clean = r.get('artistName', '').lower().replace("ö", "o").replace("ü", "u").replace("ş", "s").replace("ç", "c").replace("ğ", "g").replace("ı", "i")
                    
                    if art_clean == res_art_clean:
                        results.append(r)
            
            if results:
                song = random.choice(results)
                raw_name = song['trackName']
                clean_title = raw_name.split('(')[0].split(' - ')[0].split('[')[0].strip()
                tracks.append({
                    "artist": song['artistName'],
                    "title": clean_title,
                    "file": f"/api/proxy-audio?url={requests.utils.quote(song['previewUrl'])}"
                })
        except Exception:
            continue

    random.shuffle(tracks)
    return tracks

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/get-tracks')
def get_tracks():
    lang = request.args.get('lang', 'TR')
    if lang == 'TR':
        artist_pool = TR_HITS
    elif lang == 'EN':
        artist_pool = EN_HITS
    else:
        artist_pool = TR_HITS + EN_HITS
    tracks = fetch_itunes_tracks(artist_pool, limit=5)
    return jsonify({"tracks": tracks})

@app.route('/api/proxy-audio')
def proxy_audio():
    audio_url = request.args.get('url')
    
    # SSRF GÜVENLİK YAMASI: Sadece Apple/iTunes sunucularına giden isteklere izin ver
    if not audio_url or not audio_url.startswith("https://audio-ssl.itunes.apple.com/"):
        return "Forbidden: Invalid audio source", 403
        
    try:
        req = requests.get(audio_url, stream=True, timeout=10)
        return Response(req.iter_content(chunk_size=1024), content_type=req.headers.get('content-type', 'audio/mp4'))
    except Exception as e:
        print(f"Audio Proxy Error: {e}") # Loglama iyileştirildi
        return "Audio fetch error", 500

@app.route('/api/save-score', methods=['POST'])
def save_score():
    data = request.get_json()
    player_name = data.get('player_name', 'PLAYER')
    score = data.get('score', 0)
    lang_mode = data.get('lang_mode', 'TR')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO leaderboard (player_name, score, lang_mode) VALUES (%s, %s, %s)", (player_name, score, lang_mode))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"status": "ok"})

@app.route('/api/top-scores')
def top_scores():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT player_name, score, lang_mode FROM leaderboard ORDER BY score DESC LIMIT 10")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify([{"player_name": r[0], "score": r[1], "lang_mode": r[2]} for r in rows])

ROOMS = {}

def generate_room_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

@socketio.on('client_trigger_next')
def on_client_trigger_next(data):
    room_code = data.get('room_code')
    expected_idx = data.get('expected_idx')
    
    if room_code in ROOMS:
        room = ROOMS[room_code]
        if room.get('current_idx') == expected_idx:
            room['current_idx'] += 1
            room['round_locked'] = False
            
            if 'pass_voters' in room:
                room['pass_voters'].clear()
            if 'ready_players' in room:
                room['ready_players'].clear()
                
            idx = room['current_idx']
            total = len(room['playlist'])
            
            if idx >= total:
                emit('game_over_sync', {'players': room['players']}, room=room_code)
            else:
                emit('next_round_sync', {'track_index': idx}, room=room_code)

@socketio.on('create_room')
def on_create_room(data):
    room_code = generate_room_code()
    player_name = data.get('player_name', 'PLAYER 1')
    ROOMS[room_code] = {
        'players': [{ 'id': request.sid, 'name': player_name, 'score': 0, 'is_host': True }],
        'playlist': [],
        'current_idx': 0,
        'pass_voters': set(),
        'ready_players': set(),
        'lang_mode': data.get('lang_mode', 'TR'),
        'round_locked': False
    }
    join_room(room_code)
    emit('room_created', {'room_code': room_code, 'players': ROOMS[room_code]['players'], 'lang_mode': ROOMS[room_code]['lang_mode']})

@socketio.on('join_room_req')
def on_join_room(data):
    room_code = data.get('room_code', '').upper()
    player_name = data.get('player_name', 'PLAYER 2')
    
    if room_code not in ROOMS:
        emit('error_msg', {'msg': 'Room not found!'})
        return
    if len(ROOMS[room_code]['players']) >= 2:
        emit('error_msg', {'msg': 'Room is full!'})
        return
        
    existing_names = [p['name'].upper() for p in ROOMS[room_code]['players']]
    if player_name.upper() in existing_names:
        emit('error_msg', {'msg': 'Username already taken in this room! Please go back and choose a different name.'})
        return
        
    ROOMS[room_code]['players'].append({ 'id': request.sid, 'name': player_name, 'score': 0, 'is_host': False })
    join_room(room_code)
    emit('joined_successfully', {'room_code': room_code, 'lang_mode': ROOMS[room_code]['lang_mode']}, room=request.sid)
    emit('player_list_update', {'players': ROOMS[room_code]['players']}, room=room_code)

@socketio.on('start_multiplayer_game')
def on_start_game(data):
    room_code = data.get('room_code')
    if room_code in ROOMS:
        lang = ROOMS[room_code].get('lang_mode', 'TR')
        artist_pool = TR_HITS if lang == 'TR' else (EN_HITS if lang == 'EN' else TR_HITS + EN_HITS)
        tracks = fetch_itunes_tracks(artist_pool, limit=5)
        ROOMS[room_code]['playlist'] = tracks
        ROOMS[room_code]['current_idx'] = 0
        ROOMS[room_code]['pass_voters'] = set()
        ROOMS[room_code]['ready_players'] = set()
        ROOMS[room_code]['round_locked'] = False
        emit('game_started', {'playlist': tracks, 'players': ROOMS[room_code]['players']}, room=room_code)

@socketio.on('track_loaded')
def on_track_loaded(data):
    room_code = data.get('room_code')
    if room_code in ROOMS:
        room = ROOMS[room_code]
        room['ready_players'].add(request.sid)
        
        if len(room['ready_players']) >= len(room['players']):
            room['ready_players'].clear()
            emit('all_players_ready', {}, room=room_code)

@socketio.on('correct_guess_sync')
def on_correct_guess(data):
    room_code = data.get('room_code')
    pts = data.get('points_earned', 15)
    if room_code in ROOMS:
        room = ROOMS[room_code]
        if room.get('round_locked', False):
            return
        room['round_locked'] = True
        if 'pass_voters' in room:
            room['pass_voters'].clear()
            
        for p in room['players']:
            if p['id'] == request.sid:
                p['score'] += pts
                emit('round_winner', {
                    'winner_name': p['name'],
                    'points_earned': pts,
                    'players': room['players']
                }, room=room_code)
                break

@socketio.on('vote_pass_sync')
def on_vote_pass(data):
    room_code = data.get('room_code')
    player_name = data.get('player_name', '')
    if room_code in ROOMS:
        room = ROOMS[room_code]
        if room.get('round_locked', False):
            return
            
        if 'pass_voters' not in room:
            room['pass_voters'] = set()
            
        room['pass_voters'].add(request.sid)
        pass_count = len(room['pass_voters'])
        total_players = len(room['players'])
        
        emit('pass_voted_update', {
            'voter_name': player_name,
            'pass_count': pass_count,
            'total_players': total_players
        }, room=room_code)
        
        if pass_count >= total_players and total_players > 0:
            room['round_locked'] = True
            room['pass_voters'].clear()
            emit('both_passed_next', {}, room=room_code)

@socketio.on('timeout_sync')
def on_timeout_sync(data):
    room_code = data.get('room_code')
    if room_code in ROOMS:
        room = ROOMS[room_code]
        if not room.get('round_locked', False):
            room['round_locked'] = True
            if 'pass_voters' in room:
                room['pass_voters'].clear()
            emit('round_timeout_broadcast', {}, room=room_code)

@socketio.on('disconnect')
def on_disconnect():
    for code, room in list(ROOMS.items()):
        for p in room['players']:
            if p['id'] == request.sid:
                emit('opponent_left', {'msg': f"{p['name']} left the room."}, room=code)
                del ROOMS[code]
                break

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)