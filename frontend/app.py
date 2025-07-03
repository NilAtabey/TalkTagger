import sys
import os
import json
import random
import string
import shutil
import zipfile
import tempfile
import subprocess
import threading
import time
import socket
from datetime import datetime
from pathlib import Path
import uuid
import logging

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.utils import secure_filename

# initialize Flask app
app = Flask(__name__, 
           template_folder=os.path.dirname(os.path.abspath(__file__)),
           static_folder=os.path.dirname(os.path.abspath(__file__)),
           static_url_path='')
app.config['SECRET_KEY'] = 'talktagger-secret-key-2025'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

# initialize SocketIO
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    max_http_buffer_size=100 * 1024 * 1024,
    # Add these crucial settings:
    ping_timeout=60,          # Time to wait for pong response
    ping_interval=25,         # How often to send ping
    engineio_logger=True,     # Enable logging for debugging
    logger=True,              # Enable SocketIO logging
    transports=['websocket', 'polling'],  # Allow fallback to polling
    async_mode='threading'    # Use threading mode
)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

class GameState:
    def __init__(self):
        self.games = {}  # game_code: game_data
        self.players = {}  # session_id: player_data
        self.pipeline_status = {
            "running": False,
            "progress": 0, 
            "message": "Ready to process files", 
            "error": None,
            "completed": False
        }
        self.game_data = {}  # will hold the loaded real_data.json

    def reset_pipeline_status(self):
        """Reset pipeline status for new upload"""
        self.pipeline_status = {
            "running": False,
            "progress": 0,
            "message": "Please upload your files to start",
            "error": None,
            "completed": False
        }

    def update_pipeline_status(self, progress, message, error=None, completed=False):
        """Update pipeline status"""
        self.pipeline_status.update({
            "progress": progress,
            "message": message,
            "error": error,
            "completed": completed
        })
        socketio.emit('pipeline_status_update', self.pipeline_status) # emit status update to all connected clients


game_state = GameState() # global game state instance


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

# file paths configuration
BASE_DIR = Path(__file__).parent
ROOT_DIR = BASE_DIR.parent  # go up one level to get to project root
BACKEND_DIR = ROOT_DIR / 'backend'  # use root backend dir
DATA_DIR = BACKEND_DIR / 'data'
GAME_DATA_PATH = DATA_DIR / 'game_data.json'
CONVOS_BEFORE_DIR = BACKEND_DIR / 'convos_before'
CONVOS_AFTER_DIR = BACKEND_DIR / 'convos_after'
UPLOAD_TEMP_DIR = BASE_DIR / 'temp_uploads'
FINAL_PY_PATH = ROOT_DIR / 'final.py'  # final.py is in the root directory


for directory in [DATA_DIR, CONVOS_BEFORE_DIR, CONVOS_AFTER_DIR, UPLOAD_TEMP_DIR]: # ensure directories exist
    directory.mkdir(parents=True, exist_ok=True)

def get_available_ips():
    """Get available IP addresses for network access"""
    ips = []
    try:
        ips.append("localhost")
        
        hostname = socket.gethostname()
        ips.append(socket.gethostbyname(hostname))
        
        for interface in socket.if_nameindex():
            try:
                pass
            except:
                pass
    except Exception as e:
        print(f"[WARNING] Could not detect all IP addresses: {e}")
    
    return ips

def load_existing_game_data():
    """Load existing game data if available"""
    try:
        if GAME_DATA_PATH.exists():
            with open(GAME_DATA_PATH, 'r', encoding='utf-8') as f:
                game_state.game_data = json.load(f)
            print("[OK] Loaded existing game data from game_data.json")
            
            if game_state.game_data.get('game_rounds'): # mark pipeline completed if data exists and has game_rounds
                game_state.pipeline_status["completed"] = True
                game_state.pipeline_status["message"] = "Data ready for game creation"
    except Exception as e:
        print(f"[WARNING] Warning: Could not load existing data: {e}")

def create_game_questions():
    """Return a tuple of (real_questions, generated_questions) from game_data.json."""
    all_questions = game_state.game_data.get('game_rounds', [])
    real_questions = [q for q in all_questions if not q.get('is_synthetic', False)]
    generated_questions = [q for q in all_questions if q.get('is_synthetic', False)]
    return real_questions, generated_questions

def run_talktagger_pipeline(upload_path, platform_type="dc"):
    """Run the complete TalkTagger pipeline using final.py"""
    try:
        game_state.pipeline_status["running"] = True
        game_state.update_pipeline_status(0, "Starting TalkTagger pipeline...")
        print(f"[START] Starting TalkTagger pipeline for {platform_type} files")
        game_state.update_pipeline_status(10, "Cleaning up previous files...")
        for file_path in CONVOS_BEFORE_DIR.glob("*"):
            if file_path.is_file():
                file_path.unlink()
        game_state.update_pipeline_status(20, "Extracting uploaded files...")
        if zipfile.is_zipfile(upload_path):
            with zipfile.ZipFile(upload_path, 'r') as zip_ref:
                zip_ref.extractall(CONVOS_BEFORE_DIR)
        else:
            filename = Path(upload_path).name
            shutil.copy2(upload_path, CONVOS_BEFORE_DIR / filename)
        game_state.update_pipeline_status(30, f"Configuring pipeline for {platform_type}...")
        game_state.update_pipeline_status(40, "Running TalkTagger pipeline...") # no longer modify final.py; pass platform as env var
        print("[RUN] Executing final.py...")
        env = os.environ.copy()
        env["UPLOAD_TAG"] = platform_type
        result = subprocess.run(
            [sys.executable, str(FINAL_PY_PATH)], 
            cwd=ROOT_DIR,
            text=True, 
            timeout=300,
            env=env
        )
        if result.returncode != 0:
            error_msg = f"Pipeline failed: {result.stderr}"
            print(f"[ERROR] {error_msg}")
            raise Exception(error_msg)
        game_state.update_pipeline_status(80, "Loading processed data...")
        load_existing_game_data()
        game_state.update_pipeline_status(90, "Validating data...")
        if not (game_state.game_data.get('game_rounds')):
            raise Exception("Pipeline completed but data validation failed")
        game_state.update_pipeline_status(100, "Pipeline completed successfully!", completed=True)
        print("[OK] TalkTagger pipeline completed successfully!")
    except subprocess.TimeoutExpired:
        error_msg = "Pipeline timed out after 5 minutes"
        print(f"[ERROR] {error_msg}")
        game_state.update_pipeline_status(0, error_msg, error=error_msg)
    except Exception as e:
        error_msg = f"Pipeline failed: {str(e)}"
        print(f"[ERROR] {error_msg}")
        game_state.update_pipeline_status(0, error_msg, error=error_msg)
    finally:
        game_state.pipeline_status["running"] = False
        try:
            if os.path.exists(upload_path):
                os.remove(upload_path)
        except:
            pass

def run_pipeline_async(upload_path, platform_type="dc"):
    """Run pipeline in background thread"""
    thread = threading.Thread(
        target=run_talktagger_pipeline, 
        args=(upload_path, platform_type),
        daemon=True
    )
    thread.start()
    return thread

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

# flask Routes
@app.route('/')
def index():
    """Serve the main game page"""
    return render_template('game.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    """Handle file upload and start pipeline"""
    try:
        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        
        files = request.files.getlist('files')
        platform_type = request.form.get('platform', 'dc')
        
        if not files or files[0].filename == '':
            return jsonify({'error': 'No files selected'}), 400
        
        game_state.reset_pipeline_status()
        
        timestamp = int(time.time())
        temp_upload_path = UPLOAD_TEMP_DIR / f"upload_{timestamp}.zip"
        
        if len(files) == 1 and files[0].filename.endswith('.zip'):
            files[0].save(temp_upload_path)
        else:
            with zipfile.ZipFile(temp_upload_path, 'w') as zipf:
                for file in files:
                    if file.filename:
                        filename = secure_filename(file.filename)
                        zipf.writestr(filename, file.read())
        
        # START PIPELINE PROCESSING
        run_pipeline_async(str(temp_upload_path), platform_type)
        
        return jsonify({
            'message': 'Files uploaded successfully! Pipeline is running...',
            'status': 'processing'
        })
        
    except Exception as e:
        print(f"[ERROR] Upload error: {e}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/pipeline-status')
def get_pipeline_status():
    """Get current pipeline status"""
    return jsonify(game_state.pipeline_status)

@app.route('/debug/game-state')
def debug_game_state():
    """Debug endpoint to check game state"""
    debug_info = {
        'total_games': len(game_state.games),
        'total_players': len(game_state.players),
        'games': {}
    }
    
    for game_code, game in game_state.games.items():
        debug_info['games'][game_code] = {
            'state': game['state'],
            'current_question': game['current_question'],
            'total_questions': len(game['questions']),
            'players_count': len(game['players']),
            'host_sid': game.get('host_sid'),
            'has_start_timer': 'start_timer' in game,
            'has_question_sent_time': 'question_sent_time' in game
        }
    
    return jsonify(debug_info)

@app.route('/game-data')
def get_game_data():
    """Serve the processed game data (questions and superlatives if present)"""
    if not game_state.game_data:
        return jsonify({'error': 'No game data available'}), 404
    return jsonify(game_state.game_data)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

# Socket.IO Event Handlers
# Add connection health monitoring
@socketio.on('connect')
def on_connect():
    """Handle client connection with better logging"""
    client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ['REMOTE_ADDR'])
    print(f"[CONNECT] Client connected: {request.sid} from {client_ip}")
    
    emit('pipeline_status_update', game_state.pipeline_status) # send initial status immediately
    
    emit('connection_confirmed', {'sid': request.sid}) # send a heartbeat confirmation

@socketio.on('disconnect')
def on_disconnect():
    """Handle client disconnection with better cleanup"""
    print(f"[DISCONNECT] Client disconnected: {request.sid}")
    
    cleanup_player_from_games(request.sid) # more robust cleanup


def cleanup_player_from_games(sid):
    """Clean up player from all games they might be in"""
    try:
        if sid in game_state.players:
            player = game_state.players[sid]
            game_code = player.get('game_code')
            
            if game_code and game_code in game_state.games:
                game = game_state.games[game_code]
                
                if sid == game.get('host_sid'):
                    game['host_disconnected'] = True
                    game['host_disconnect_time'] = time.time()
                    cleanup_game_timers(game_code)
                    print(f"[HOST_DISCONNECT] Host disconnected from game {game_code}")
                
                # Remove player from game (only if they were actually a player, not display-only host)
                if sid in game['players']:
                    player_name = game['players'][sid]['name']
                    del game['players'][sid]
                    
                    # Notify other players
                    socketio.emit('player_left', {
                        'player_name': player_name,
                        'players_count': len(game['players'])
                    }, room=game_code)
                
                # Only remove empty games that aren't waiting for host reconnection
                if (len(game['players']) == 0 and 
                    not game.get('host_disconnected', False)):
                    cleanup_game_timers(game_code)  # Clean up timers before deleting
                    del game_state.games[game_code]
                    print(f"🗑️ Removed empty game: {game_code}")
            
            del game_state.players[sid]
    
    except Exception as e:
        print(f"[ERROR] Error during cleanup: {e}")
        
# additional helper function to get player count (excluding host):
def get_actual_player_count(game):
    """Get count of actual players (excluding display-only host)"""
    return len(game['players'])  # host is not in this dict anymore

# add heartbeat mechanism
@socketio.on('heartbeat')
def on_heartbeat():
    """Handle client heartbeat"""
    emit('heartbeat_response', {'timestamp': time.time()})

@socketio.on('create_game')
def on_create_game(data):
    """Create game with host as display-only (not a player)"""
    try:
        print(f"[CREATE_GAME] Request from {request.sid}: {data}")
        
        # Host name is optional since they're not playing
        host_name = data.get('player_name', 'Host Display')
        real_questions, generated_questions = create_game_questions()
        
        if not real_questions and not generated_questions:
            print(f"[CREATE_GAME] No questions available for {request.sid}")
            emit('error', {'message': 'No game data available. Please upload files first.'})
            return
        
        game_code = generate_game_code()
        host_token = str(uuid.uuid4())
        
        # Create game - host is NOT added to players
        game_state.games[game_code] = {
            'code': game_code,
            'players': {},  # Host is NOT in this dict
            'real_questions': real_questions,
            'generated_questions': generated_questions,
            'current_phase': 1,
            'current_question_1': 0,
            'current_question_2': 0,
            'state': 'lobby',
            'scores': {},
            'answers': {},
            'created_at': datetime.now().isoformat(),
            'host_sid': request.sid,
            'host_token': host_token,
            'host_disconnected': False,
            'host_name': host_name  # Store for display purposes only
        }
        
        # Add host to tracking but mark as display-only
        game_state.players[request.sid] = {
            'name': host_name,
            'game_code': game_code,
            'is_host': True,
            'is_display_only': True  # New flag
        }
        
        # Host is NOT added to game['players'] - they're display only
        
        # Join room
        join_room(game_code)
        
        # Send confirmation
        emit('game_created', {
            'game_code': game_code,
            'host_name': host_name,
            'host_token': host_token,
            'success': True,
            'is_display_only': True
        })
        
        print(f"[GAME] Game created successfully: {game_code} by {host_name} (display only)")
        
    except Exception as e:
        print(f"[ERROR] Failed to create game: {e}")
        emit('error', {'message': f'Failed to create game: {str(e)}'})

# Improve join_game with better error handling
@socketio.on('join_game')
def on_join_game(data):
    """Join game with better error handling and confirmation"""
    try:
        print(f"[JOIN_GAME] Request from {request.sid}: {data}")
        
        game_code = data.get('game_code', '').upper().strip()
        player_name = data.get('player_name', 'Anonymous').strip()
        
        if not game_code or not player_name:
            emit('error', {'message': 'Game code and player name are required!'})
            return
        
        if game_code not in game_state.games:
            emit('error', {'message': f'Game {game_code} not found!'})
            return
        
        game = game_state.games[game_code]
        
        if game['state'] != 'lobby':
            emit('error', {'message': 'Game has already started!'})
            return
        
        # Check for duplicate names
        existing_names = [p['name'].lower() for p in game['players'].values()]
        if player_name.lower() in existing_names:
            emit('error', {'message': 'Name already taken! Please choose a different name.'})
            return
        
        # Add player to game
        game_state.players[request.sid] = {
            'name': player_name,
            'game_code': game_code,
            'is_host': False
        }
        
        game['players'][request.sid] = {
            'name': player_name,
            'score': 0
        }
        
        join_room(game_code)
        
        # Get updated players list
        players_list = [p['name'] for p in game['players'].values()]
        
        # Notify all players in the room
        socketio.emit('player_joined', {
            'player_name': player_name,
            'players': players_list,
            'players_count': len(players_list)
        }, room=game_code)
        
        # Send confirmation to the joining player
        emit('joined_game', {
            'game_code': game_code,
            'player_name': player_name,
            'players': players_list,
            'success': True
        })
        
        print(f"[JOIN] Player {player_name} successfully joined game {game_code}")
        
    except Exception as e:
        print(f"[ERROR] Failed to join game: {e}")
        emit('error', {'message': f'Failed to join game: {str(e)}'})        

def on_join_game(data):
    """Join an existing game"""
    game_code = data.get('game_code', '').upper()
    player_name = data.get('player_name', 'Anonymous')
    
    if game_code not in game_state.games:
        emit('error', {'message': 'Game not found!'})
        return
    
    game = game_state.games[game_code]
    
    if game['state'] != 'lobby':
        emit('error', {'message': 'Game already started!'})
        return
    
    # Add player to game
    player_token = data.get('player_token') or str(uuid.uuid4())
    game_state.players[request.sid] = {
        'name': player_name,
        'game_code': game_code,
        'is_host': False,
        'player_token': player_token
    }
    
    game['players'][request.sid] = {
        'name': player_name,
        'score': 0,
        'player_token': player_token
    }
    
    join_room(game_code)
    
    # Notify all players
    players_list = [p['name'] for p in game['players'].values()]
    socketio.emit('player_joined', {
        'player_name': player_name,
        'players': players_list,
        'players_count': len(players_list)
    }, room=game_code)
    
    emit('joined_game', {
        'game_code': game_code,
        'player_name': player_name,
        'players': players_list,
        'player_token': player_token
    })
    
    print(f"[JOIN] Player {player_name} joined game {game_code}")

# 2. Modify start_game to check for actual players:
@socketio.on('start_game')
def on_start_game():
    """Start the game (host only) - check for actual players, not including host"""
    # Find if this session is a host of any game
    game_code = None
    for code, game in game_state.games.items():
        if game.get('host_sid') == request.sid:
            game_code = code
            break
    
    if not game_code:
        emit('error', {'message': 'Only the host can start the game!'})
        return
    
    game = game_state.games[game_code]
    
    # Check for actual players (host is not a player)
    if len(game['players']) < 1:
        emit('error', {'message': 'Need at least 1 player to start! (Host is display only)'})
        return
    
    # Start the game
    game['state'] = 'playing'
    
    # Emit game started event
    socketio.emit('game_started', {
        'total_rounds': len(game['real_questions']) + len(game['generated_questions'])
    }, room=game_code)
    
    print(f"[START] Game {game_code} started with {len(game['players'])} players (host is display only)")
    
    # Send the first question
    send_next_question_immediate(game_code)

# 3. Modify send_next_question_immediate to handle host display properly:
def send_next_question_immediate(game_code):
    print(f"[DEBUG] send_next_question_immediate called for game_code: {game_code}")
    if game_code not in game_state.games:
        print(f"[ERROR] Game {game_code} not found!")
        return
    
    game = game_state.games[game_code]
    
    # Determine which phase and question index
    if game['current_phase'] == 1:
        questions = game['real_questions']
        idx = game['current_question_1']
        phase = 'real'
    else:
        questions = game['generated_questions']
        idx = game['current_question_2']
        phase = 'generated'
    
    if idx >= len(questions):
        # If phase 1 is done, move to phase 2
        if game['current_phase'] == 1 and game['generated_questions']:
            game['current_phase'] = 2
            game['current_question_2'] = 0
            send_next_question_immediate(game_code)
            return
        else:
            print("[DEBUG] All questions sent, ending game.")
            end_game(game_code)
            return
    
    question = questions[idx]
    print(f"[DEBUG] Preparing question: {question['message'][:50]}...")
    
    # Clear previous question state
    game['answers'] = {}
    game['question_sent_time'] = datetime.now().timestamp()
    game['ready_players'] = set()
    game['_results_shown'] = False
    
    # IMPORTANT: Cancel any existing timer for this game
    if 'question_timer' in game:
        try:
            game['question_timer'].cancel()
            print(f"[TIMER] Cancelled previous timer for game {game_code}")
        except:
            pass
    
    # Send question to HOST (display only - shows question and options)
    host_sid = game.get('host_sid')
    if host_sid:
        socketio.emit('host_question', {
            'question_number': idx + 1,
            'total_questions': len(questions),
            'message': question['message'],
            'options': question['choices'],
            'type': phase,
            'phase': phase,
            'player_count': len(game['players'])  # Show how many players are answering
        }, room=host_sid)

    # Send question to PLAYERS (they only see options, not the full message)
    for sid in game['players']:
        socketio.emit('player_question', {
            'question_number': idx + 1,
            'total_questions': len(questions),
            'options': question['choices'],
            'type': phase,
            'phase': phase
        }, room=sid)
    
    # Create a more reliable timer using threading.Timer
    def question_timer_callback():
        print(f"[TIMER] 15 seconds expired for game {game_code}, checking for unanswered players.")
        
        # Double-check game still exists
        if game_code not in game_state.games:
            print(f"[TIMER] Game {game_code} no longer exists, timer cancelled")
            return
        
        current_game = game_state.games[game_code]
        
        # Check if results were already shown (race condition protection)
        if current_game.get('_results_shown', False):
            print(f"[TIMER] Results already shown for game {game_code}, timer cancelled")
            return
        
        # Add null answers for players who didn't respond
        for sid in current_game['players']:
            if sid not in current_game['answers']:
                player = game_state.players.get(sid)
                current_game['answers'][sid] = {
                    'answer': None,
                    'player_name': player['name'] if player else 'Unknown',
                    'timestamp': datetime.now().isoformat()
                }
                print(f"[TIMER] Added null answer for player {player['name'] if player else 'Unknown'}")
        
        # Mark results as shown and show them
        current_game['_results_shown'] = True
        show_question_results(game_code)
    
    import threading
    timer = threading.Timer(15.0, question_timer_callback)
    game['question_timer'] = timer
    timer.start()
    
    print(f"[TIMER] Started 15-second timer for game {game_code}")

@socketio.on('request_first_question')
def on_request_first_question():
    """Fallback: Client requests first question if timer fails"""
    print(f"[FALLBACK] Client {request.sid} requested first question")
    
    game_code = None
    
    # Check if this is a host
    for code, game in game_state.games.items():
        if game.get('host_sid') == request.sid:
            game_code = code
            break
    
    # If not a host, check if this is a player
    if not game_code and request.sid in game_state.players:
        player = game_state.players[request.sid]
        game_code = player['game_code']
    
    if not game_code:
        print(f"[FALLBACK] No game found for client {request.sid}")
        emit('error', {'message': 'You are not in a game!'})
        return
    
    if game_code not in game_state.games:
        print(f"[FALLBACK] Game {game_code} not found")
        emit('error', {'message': 'Game not found!'})
        return
    
    game = game_state.games[game_code]
    
    # Only allow this if game is in playing state and no question has been sent yet
    if (game['state'] == 'playing' and 
        game['current_question'] == 0 and
        not game.get('question_sent_time')):  # Check if no question sent yet
        
        print(f"[FALLBACK] Processing first question request for game {game_code}")
        send_next_question_immediate(game_code)
    else:
        print(f"[FALLBACK] Request denied - game state: {game['state']}, current_question: {game['current_question']}, question_sent: {game.get('question_sent_time') is not None}")

# 4. Modify submit_answer to exclude host:
@socketio.on('submit_answer')
def on_submit_answer(data):
    """Handle answer submission - only from actual players, not host"""
    if request.sid not in game_state.players:
        emit('error', {'message': 'You are not in a game!'})
        return
    
    player = game_state.players[request.sid]
    
    # Check if this is the host (display only)
    if player.get('is_display_only', False):
        emit('error', {'message': 'Host cannot submit answers! You are display only.'})
        return
    
    game_code = player['game_code']
    answer = data.get('answer')
    
    if game_code not in game_state.games:
        emit('error', {'message': 'Game not found!'})
        return
    
    game = game_state.games[game_code]
    
    if game['state'] != 'playing':
        emit('error', {'message': 'Game is not active!'})
        return
    
    # Check if results were already shown (prevent late answers)
    if game.get('_results_shown', False):
        emit('error', {'message': 'Question time has expired!'})
        return
    
    # Store answer
    game['answers'][request.sid] = {
        'answer': answer,
        'player_name': player['name'],
        'timestamp': datetime.now().isoformat()
    }
    
    print(f"[ANSWER] {player['name']} answered: {answer}")
    
    # Check if all PLAYERS (not including host) answered
    if len(game['answers']) == len(game['players']):
        print(f"[ANSWER] All players answered for game {game_code}")
        
        # Cancel the timer since everyone answered
        if 'question_timer' in game:
            try:
                game['question_timer'].cancel()
                print(f"[TIMER] Cancelled timer for game {game_code} - all players answered")
            except:
                pass
        
        # Only show results if not already shown
        if not game.get('_results_shown', False):
            game['_results_shown'] = True
            show_question_results(game_code)

# 5. Modify player_ready to exclude host:
@socketio.on('player_ready')
def on_player_ready():
    """Handle player ready for next round - only actual players, not host"""
    if request.sid not in game_state.players:
        emit('error', {'message': 'You are not in a game!'})
        return
    
    player = game_state.players[request.sid]
    
    # Check if this is the host (display only)
    if player.get('is_display_only', False):
        # Host doesn't need to be "ready" - they control the flow
        return
    
    game_code = player['game_code']
    
    if game_code not in game_state.games:
        emit('error', {'message': 'Game not found!'})
        return
    
    game = game_state.games[game_code]
    
    if 'ready_players' not in game:
        game['ready_players'] = set()
    
    game['ready_players'].add(request.sid)
    
    # If all PLAYERS (not including host) are ready, notify host to advance
    if len(game['ready_players']) == len(game['players']):
        host_sid = game.get('host_sid')
        if host_sid:
            socketio.emit('all_players_ready', {}, room=host_sid)

def show_question_results(game_code):
    if game_code not in game_state.games:
        return
    game = game_state.games[game_code]
    # Determine which phase and question index
    if game['current_phase'] == 1:
        questions = game['real_questions']
        idx = game['current_question_1']
        phase = 'real'
    else:
        questions = game['generated_questions']
        idx = game['current_question_2']
        phase = 'generated'
    question = questions[idx]
    correct_answer = question['correct_author']
    results = []
    for player_sid, answer_data in game['answers'].items():
        player_data = game['players'][player_sid]
        is_correct = answer_data['answer'] == correct_answer
        answer_time = datetime.fromisoformat(answer_data['timestamp']).timestamp()
        sent_time = game.get('question_sent_time', answer_time)
        time_taken = answer_time - sent_time
        time_left = max(0, 15 - time_taken)
        if time_left > 12:
            speed_bonus = 5
        elif time_left > 8:
            speed_bonus = 3
        elif time_left > 4:
            speed_bonus = 1
        else:
            speed_bonus = 0
        if phase == 'generated':
            base_points = 20
            speed_bonus = speed_bonus * 2
        else:
            base_points = 10
        points_earned = base_points + speed_bonus if is_correct else 0
        player_data['score'] += points_earned
        results.append({
            'player_name': answer_data['player_name'],
            'answer': answer_data['answer'],
            'correct': is_correct,
            'points_earned': points_earned,
            'total_score': player_data['score'],
            'time_taken': round(time_taken, 2),
            'time_left': round(time_left, 2)
        })
    leaderboard = sorted(
        [{'name': p['name'], 'score': p['score']} for p in game['players'].values()],
        key=lambda x: x['score'],
        reverse=True
    )
    distinctiveness_score = question.get('distinctiveness_score', None)
    bert_similarity = question.get('bert_similarity', None)
    explanation = f"Distinctiveness Score: {distinctiveness_score}" if distinctiveness_score is not None else ""
    for sid in game['players']:
        view = 'host' if sid == game.get('host_sid') else 'player'
        player_name = game['players'][sid]['name']
        standing = next((i+1 for i, entry in enumerate(leaderboard) if entry['name'] == player_name), None)
        socketio.emit('question_results', {
            'correct_answer': correct_answer,
            'message': question['message'],
            'results': results,
            'leaderboard': leaderboard,
            'distinctiveness_score': distinctiveness_score,
            'bert_similarity': bert_similarity,
            'explanation': explanation,
            'view': view,
            'standing': standing,
            'phase': phase
        }, room=sid)
    host_sid = game.get('host_sid')
    if host_sid:
        socketio.emit('question_results', {
            'correct_answer': correct_answer,
            'message': question['message'],
            'results': results,
            'leaderboard': leaderboard,
            'distinctiveness_score': distinctiveness_score,
            'bert_similarity': bert_similarity,
            'explanation': explanation,
            'view': 'host',
            'standing': None,
            'phase': phase
        }, room=host_sid)
    # Advance question index for the current phase
    if game['current_phase'] == 1:
        game['current_question_1'] += 1
    else:
        game['current_question_2'] += 1

def end_game(game_code):
    """End the game and show final results"""
    if game_code not in game_state.games:
        return
        
    game = game_state.games[game_code]
    game['state'] = 'finished'
    
    # Clean up any active timers
    cleanup_game_timers(game_code)
    
    # Final leaderboard
    final_leaderboard = sorted(
        [{'name': p['name'], 'score': p['score']} for p in game['players'].values()],
        key=lambda x: x['score'],
        reverse=True
    )
    
    winner = final_leaderboard[0]['name'] if final_leaderboard else 'No one'
    total_questions = len(game.get('real_questions', [])) + len(game.get('generated_questions', []))
    
    socketio.emit('game_finished', {
        'leaderboard': final_leaderboard,
        'winner': winner,
        'total_questions': total_questions
    }, room=game_code)
    
    print(f"[FINISH] Game {game_code} finished! Winner: {winner}")

@socketio.on('check_pipeline_status')
def on_check_pipeline_status():
    """Send current pipeline status to requesting client"""
    emit('pipeline_status_update', game_state.pipeline_status)

@socketio.on('next_round')
def on_next_round():
    # Find if this session is a host of any game
    game_code = None
    for code, game in game_state.games.items():
        if game.get('host_sid') == request.sid:
            game_code = code
            break

    if not game_code:
        emit('error', {'message': 'Only the host can advance the round!'})
        return

    game = game_state.games[game_code]

    # Determine which phase and question index
    if game['current_phase'] == 1:
        questions = game['real_questions']
        idx = game['current_question_1']
    else:
        questions = game['generated_questions']
        idx = game['current_question_2']

    if idx < len(questions):
        send_next_question_immediate(game_code)
    else:
        # If phase 1 is done and phase 2 exists, move to phase 2
        if game['current_phase'] == 1 and game['generated_questions']:
            game['current_phase'] = 2
            game['current_question_2'] = 0
            send_next_question_immediate(game_code)
        else:
            end_game(game_code)

# New event for host reconnection
def find_game_by_host_token(host_token):
    for game in game_state.games.values():
        if game.get('host_token') == host_token:
            return game
    return None

# Add connection recovery for hosts
@socketio.on('host_reconnect')
def on_host_reconnect(data):
    """Improved host reconnection"""
    try:
        host_token = data.get('host_token')
        if not host_token:
            emit('error', {'message': 'Invalid host token'})
            return
        
        game = find_game_by_host_token(host_token)
        if not game:
            emit('error', {'message': 'Game not found or expired'})
            return
        
        # Update host session
        old_host_sid = game.get('host_sid')
        game['host_sid'] = request.sid
        game['host_disconnected'] = False
        
        # Update player tracking
        if old_host_sid in game_state.players:
            # Transfer player data to new session
            player_data = game_state.players[old_host_sid]
            del game_state.players[old_host_sid]
            
            game_state.players[request.sid] = player_data
            
            # Update game players dict
            if old_host_sid in game['players']:
                game['players'][request.sid] = game['players'][old_host_sid]
                del game['players'][old_host_sid]
        
        join_room(game['code'])
        
        emit('host_reconnected', {
            'game_code': game['code'],
            'success': True,
            'game_state': game['state']
        })
        
        print(f"[RECONNECT] Host successfully reconnected to game {game['code']}")
        
    except Exception as e:
        print(f"[ERROR] Host reconnection failed: {e}")
        emit('error', {'message': f'Reconnection failed: {str(e)}'})



@socketio.on('player_reconnect')
def on_player_reconnect(data):
    player_token = data.get('player_token')
    player_name = data.get('player_name')
    game_code = data.get('game_code')
    if not (player_token and player_name and game_code):
        return
    if game_code not in game_state.games:
        return
    game = game_state.games[game_code]
    # Find old SID by token
    old_sid = None
    for sid, pdata in game_state.players.items():
        if pdata.get('player_token') == player_token:
            old_sid = sid
            break
    # Remove old SID if present
    if old_sid and old_sid != request.sid:
        del game_state.players[old_sid]
        if old_sid in game['players']:
            del game['players'][old_sid]
    # Re-associate new SID
    game_state.players[request.sid] = {
        'name': player_name,
        'game_code': game_code,
        'is_host': False,
        'player_token': player_token
    }
    game['players'][request.sid] = {
        'name': player_name,
        'score': 0 if old_sid is None else game['players'][old_sid]['score'],
        'player_token': player_token
    }
    join_room(game_code)
    emit('joined_game', {
        'game_code': game_code,
        'player_name': player_name,
        'players': [p['name'] for p in game['players'].values()],
        'player_token': player_token
    })
    print(f"[RECONNECT] Player {player_name} reconnected to game {game_code}")

# Error Handlers
@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large. Maximum size is 100MB.'}), 413

@app.errorhandler(Exception)
def handle_exception(e):
    print(f"[ERROR] Unhandled exception: {e}")
    return jsonify({'error': 'An unexpected error occurred'}), 500

def generate_game_code():
    """Generate a unique 4-letter game code."""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase, k=4))
        if code not in game_state.games:
            return code


# Add periodic cleanup of orphaned games
def cleanup_orphaned_games():
    """Clean up games with disconnected hosts after timeout"""
    current_time = time.time()
    to_remove = []
    
    for game_code, game in game_state.games.items():
        if (game.get('host_disconnected', False) and 
            current_time - game.get('host_disconnect_time', 0) > 300):  # 5 minutes
            to_remove.append(game_code)
    
    for game_code in to_remove:
        del game_state.games[game_code]
        print(f"🗑️ Cleaned up orphaned game: {game_code}")

# Run cleanup every 5 minutes
def start_cleanup_task():
    def cleanup_loop():
        while True:
            time.sleep(300)  # 5 minutes
            cleanup_orphaned_games()
    
    cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
    cleanup_thread.start()

def cleanup_game_timers(game_code):
    """Clean up any active timers for a game"""
    if game_code in game_state.games:
        game = game_state.games[game_code]
        if 'question_timer' in game:
            try:
                game['question_timer'].cancel()
                print(f"[CLEANUP] Cancelled timer for game {game_code}")
            except:
                pass
            del game['question_timer']

# Update the main startup section
if __name__ == '__main__':
    print("=" * 60)
    print("[SERVER] TALKTAGGER SERVER STARTING")
    print("=" * 60)
    
    # Enable logging for debugging
    logging.basicConfig(level=logging.INFO)
    
    # Load existing data
    load_existing_game_data()
    
    # Start cleanup task
    start_cleanup_task()
    
    print("[INFO] Starting server with improved connection handling...")
    
    # Get and display available IP addresses
    available_ips = get_available_ips()
    for ip in available_ips:
        print(f"[URL] http://{ip}:5000")
    
    print("=" * 60)
    
    # Start the server with better configuration
    socketio.run(
        app, 
        host='0.0.0.0',
        port=5000, 
        debug=False,
        allow_unsafe_werkzeug=True,
        use_reloader=False  # Prevent double startup in debug mode
    )