import os
import random
import string
import sqlite3
import requests
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'guesstrack_super_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

DB_NAME = 'scores.db'

# Güncel Sanatçı Listeleri
TR_HITS = [
    "Duman", "Mor ve Otesi", "maNga", "Sebnem Ferah", "Teoman",
    "Sakin", "Vega", "Kurban", "Adamlar", "Athena", "Yuksek Sadakat",
    "Can Bonomo", "Baris Manco", "Cem Karaca", "Erkin Koray", "Cilekes", 
    "Redd", "Ozlem Tekin", "Onur Ozdemir", "Birsen Tezer", "Model",
    "Tarkan", "Sertab Erener", "Kenan Dogulu", "Levent Yuksel", "Nazan Öncel", "Göksel"
]

EN_HITS = [
    "Nirvana", "Jeff Buckley", "Elvis Presley", "Red Hot Chili Peppers", "Queen", 
    "Bon Jovi", "Marilyn Manson", "The Cranberries", "Metallica", "Tamino",
    "Britney Spears", "Michael Jackson", "Rihanna", "Madonna", "Deftones", 
    "AC/DC", "Eminem", "Kanye West", "Katy Perry", "Selena Gomez"
]

active_rooms = {}

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leaderboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT,
            score INTEGER,
            lang_mode TEXT
        )
    ''')
    conn.commit()
    conn.close()

def generate_room_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

def fetch_tracks(lang_mode, count=5):
    artists = []
    if lang_mode == 'TR':
        artists = TR_HITS
    elif lang_mode == 'EN':
        artists = EN_HITS
    else:
        artists = TR_HITS + EN_HITS

    selected_artists = random.sample(artists, min(len(artists), count * 2))
    tracks = []
    
    for artist in selected_artists:
        if len(tracks) >= count:
            break
            
        # ÇİFTE GÜVENLİK 1: strict=on ile Deezer'ı zorluyoruz
        url = f'https://api.deezer.com/search?q=artist:"{artist}"&strict=on'
        try:
            response = requests.get(url, timeout=3)
            data = response.json()
            if 'data' in data:
                valid_songs = []
                for t in data['data']:
                    # ÇİFTE GÜVENLİK 2: Gelen şarkının sanatçısı ile aradığımız sanatçı eşleşiyor mu? (Sibel Can engeli)
                    if t.get('preview') and artist.lower() in t['artist']['name'].lower():
                        valid_songs.append(t)

                if valid_songs:
                    track = random.choice(valid_songs)
                    
                    # İSİM TEMİZLİĞİ: Radio Edit, Remastered, feat. vs çöpe gidiyor
                    raw_title = track.get('title_short', track['title'])
                    clean_title = raw_title.split(' - ')[0].split(' (')[0].split(' [')[0].split(' feat')[0].split(' ft')[0].strip()
                    
                    tracks.append({
                        'title': clean_title,
                        'artist': track['artist']['name'],
                        'file': track['preview']
                    })
        except Exception as e:
            print(f"API Hatası ({artist}):", e)

    while len(tracks) < count and tracks:
        tracks.append(random.choice(tracks))
        
    return tracks

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/get-tracks')
def get_tracks_api():
    lang = request.args.get('lang', 'TR')
    tracks = fetch_tracks(lang, count=5)
    return jsonify({'tracks': tracks})

@app.route('/api/save-score', methods=['POST'])
def save_score():
    data = request.json
    player_name = data.get('player_name', 'GUEST')
    score = data.get('score', 0)
    lang_mode = data.get('lang_mode', 'TR')

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO leaderboard (player_name, score, lang_mode) VALUES (?, ?, ?)',
                   (player_name, score, lang_mode))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})


@socketio.on('create_room')
def handle_create_room(data):
    room_code = generate_room_code()
    while room_code in active_rooms:
        room_code = generate_room_code()

    player_name = data.get('player_name', 'HOST')
    lang_mode = data.get('lang_mode', 'TR')

    active_rooms[room_code] = {
        'lang_mode': lang_mode,
        'players': [{'sid': request.sid, 'name': player_name, 'score': 0, 'is_host': True}],
        'playlist': [],
        'current_track': 0,
        'loaded_count': 0,
        'pass_votes': []
    }

    join_room(room_code)
    emit('room_created', {'room_code': room_code, 'lang_mode': lang_mode})
    emit('player_list_update', {'players': active_rooms[room_code]['players']}, room=room_code)

@socketio.on('join_room_req')
def handle_join_room(data):
    room_code = data.get('room_code', '').strip().upper()
    player_name = data.get('player_name', 'GUEST')

    if room_code not in active_rooms:
        emit('error_msg', {'msg': 'Room not found!'})
        return

    room = active_rooms[room_code]
    if len(room['players']) >= 2:
        emit('error_msg', {'msg': 'Room is full!'})
        return

    room['players'].append({'sid': request.sid, 'name': player_name, 'score': 0, 'is_host': False})
    join_room(room_code)

    emit('joined_successfully', {'room_code': room_code, 'lang_mode': room['lang_mode']})
    emit('player_list_update', {'players': room['players']}, room=room_code)

@socketio.on('start_multiplayer_game')
def handle_start_multi_game(data):
    room_code = data.get('room_code')
    if room_code in active_rooms:
        room = active_rooms[room_code]
        room['playlist'] = fetch_tracks(room['lang_mode'], count=5)
        room['current_track'] = 0
        room['loaded_count'] = 0
        room['pass_votes'] = []

        emit('game_started', {
            'playlist': room['playlist'],
            'players': room['players']
        }, room=room_code)

@socketio.on('track_loaded')
def handle_track_loaded(data):
    room_code = data.get('room_code')
    if room_code in active_rooms:
        room = active_rooms[room_code]
        room['loaded_count'] += 1
        if room['loaded_count'] >= len(room['players']):
            room['loaded_count'] = 0
            emit('all_players_ready', room=room_code)

@socketio.on('correct_guess_sync')
def handle_correct_guess(data):
    room_code = data.get('room_code')
    points = data.get('points_earned', 10)

    if room_code in active_rooms:
        room = active_rooms[room_code]
        winner_name = ""
        for p in room['players']:
            if p['sid'] == request.sid:
                p['score'] += points
                winner_name = p['name']
                break

        emit('round_winner', {
            'winner_name': winner_name,
            'points_earned': points,
            'players': room['players']
        }, room=room_code)

@socketio.on('vote_pass_sync')
def handle_vote_pass(data):
    room_code = data.get('room_code')
    player_name = data.get('player_name')

    if room_code in active_rooms:
        room = active_rooms[room_code]
        if player_name not in room['pass_votes']:
            room['pass_votes'].append(player_name)

        pass_count = len(room['pass_votes'])
        total_players = len(room['players'])

        emit('pass_voted_update', {
            'voter_name': player_name,
            'pass_count': pass_count,
            'total_players': total_players
        }, room=room_code)

        if pass_count >= total_players:
            room['pass_votes'] = []
            emit('both_passed_next', room=room_code)

@socketio.on('timeout_sync')
def handle_timeout(data):
    room_code = data.get('room_code')
    if room_code in active_rooms:
        emit('round_timeout_broadcast', room=room_code)

@socketio.on('host_trigger_next')
def handle_host_next(data):
    room_code = data.get('room_code')
    if room_code in active_rooms:
        room = active_rooms[room_code]
        room['current_track'] += 1
        room['pass_votes'] = []

        if room['current_track'] >= len(room['playlist']):
            emit('game_over_sync', {'players': room['players']}, room=room_code)
            del active_rooms[room_code]
        else:
            emit('next_round_sync', {'track_index': room['current_track']}, room=room_code)

@socketio.on('disconnect')
def handle_disconnect():
    for room_code, room in list(active_rooms.items()):
        for p in room['players']:
            if p['sid'] == request.sid:
                emit('opponent_left', room=room_code)
                del active_rooms[room_code]
                break

if __name__ == '__main__':
    init_db()
    socketio.run(app, debug=True)