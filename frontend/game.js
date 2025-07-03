// Game State
let gameState = {
    isHost: false,
    roomCode: '',
    playerName: '',
    players: [],
    currentRound: 0, // overall round number
    totalRounds: 0, // total across both phases
    gameData: null,
    scores: {},
    timer: null,
    timeLeft: 15,
    selectedAnswer: null,
    phase: 'real', // 'real' or 'generated'
    answers: {},
    countdownTimer: null,
    fallbackTimer: null,
    phase1Index: 0,
    phase2Index: 0
};

// Sample game data for testing
const sampleGameData = {
    "selected_messages": {
        "niltheoverkill": [
            { "message": "Do i look like a doctor bro", "distinctiveness_score": 7.45 },
            { "message": "this is what it should look like", "distinctiveness_score": 7.38 }
        ],
        "endangerednoodle.": [
            { "message": "i just feel like maybe the shading shouldn't be so", "distinctiveness_score": 12.79 },
            { "message": "honestly, i might start by cleaning up some of the outliers", "distinctiveness_score": 9.39 }
        ]
    },
    "game_rounds": [
        {
            "round": 1,
            "message": "Do i look like a doctor bro",
            "correct_author": "niltheoverkill",
            "choices": ["endangerednoodle.", "ttofuu", "niltheoverkill", "mangoffee1st"],
            "difficulty_score": 7.45
        },
        {
            "round": 2,
            "message": "honestly, i might start by cleaning up some of the outliers",
            "correct_author": "endangerednoodle.",
            "choices": ["endangerednoodle.", "ttofuu", "niltheoverkill", "mangoffee1st"],
            "difficulty_score": 9.39
        }
    ]
};

// Screen Navigation
function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(screen => {
        screen.classList.remove('active');
    });
    document.getElementById(screenId).classList.add('active');
}

function showHomepage() {
    showScreen('homepage');
    resetGameState();
}

function showHostSetup() {
    showScreen('hostSetup');
    setupFileUpload();
    // Hide spinner initially
    const loadingSpinner = document.querySelector('#pipelineProgress .loading');
    if (loadingSpinner) loadingSpinner.style.display = 'none';
}

function resetGameState() {
    gameState = {
        isHost: false,
        roomCode: '',
        playerName: '',
        players: [],
        currentRound: 0,
        totalRounds: 0,
        gameData: null,
        scores: {},
        timer: null,
        timeLeft: 15,
        selectedAnswer: null,
        phase: 'real',
        answers: {},
        countdownTimer: null,
        fallbackTimer: null,
        phase1Index: 0,
        phase2Index: 0
    };
    clearInterval(gameState.timer);
    if (gameState.countdownTimer) {
        clearTimeout(gameState.countdownTimer);
    }
    if (gameState.fallbackTimer) {
        clearTimeout(gameState.fallbackTimer);
    }
}

// File Upload Setup
function setupFileUpload() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const uploadBtn = document.getElementById('uploadBtn');
    const createGameBtn = document.getElementById('createGameBtn');

    uploadArea.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('dragover', handleDragOver);
    uploadArea.addEventListener('drop', handleDrop);
    fileInput.addEventListener('change', handleFileSelect);

    function handleDragOver(e) {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    }

    function handleDrop(e) {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const files = e.dataTransfer.files;
        processFiles(files);
    }

    function handleFileSelect(e) {
        processFiles(e.target.files);
    }

    function processFiles(files) {
        if (files.length > 0) {
            // Show selected files
            const filesList = document.getElementById('filesList');
            const selectedFiles = document.getElementById('selectedFiles');

            filesList.innerHTML = '';
            Array.from(files).forEach(file => {
                const li = document.createElement('li');
                li.textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
                filesList.appendChild(li);
            });

            selectedFiles.classList.remove('hidden');
            uploadBtn.disabled = false;

            // Store files for upload
            window.selectedFiles = files;
        }
    }
}

// File Upload and Pipeline Processing
function uploadFiles() {
    if (!window.selectedFiles || window.selectedFiles.length === 0) {
        alert('Please select files first');
        return;
    }

    const platform = document.querySelector('input[name="platform"]:checked').value;
    const uploadBtn = document.getElementById('uploadBtn');
    const createGameBtn = document.getElementById('createGameBtn');
    const pipelineStatus = document.getElementById('pipelineStatus');

    // Disable upload button and show pipeline status
    uploadBtn.disabled = true;
    pipelineStatus.classList.remove('hidden');

    // Create FormData for file upload
    const formData = new FormData();
    formData.append('platform', platform);

    Array.from(window.selectedFiles).forEach(file => {
        formData.append('files', file);
    });

    // Upload files
    fetch('/upload', {
        method: 'POST',
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }

            // Start monitoring pipeline progress
            monitorPipelineProgress();
        })
        .catch(error => {
            console.error('Upload failed:', error);
            document.getElementById('pipelineError').textContent = error.message;
            document.getElementById('pipelineError').classList.remove('hidden');
            uploadBtn.disabled = false;
        });
}

// Monitor pipeline progress
function monitorPipelineProgress() {
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const pipelineMessage = document.getElementById('pipelineMessage');
    const createGameBtn = document.getElementById('createGameBtn');
    const uploadBtn = document.getElementById('uploadBtn');
    const loadingSpinner = document.querySelector('#pipelineProgress .loading');

    function checkProgress() {
        fetch('/pipeline-status')
            .then(response => response.json())
            .then(data => {
                // Update progress bar
                progressBar.style.width = `${data.progress}%`;
                progressText.textContent = `${data.progress}%`;
                pipelineMessage.textContent = data.message;

                // Spinner logic
                if (loadingSpinner) {
                    if (data.progress === 0) {
                        loadingSpinner.style.display = 'none';
                    } else {
                        loadingSpinner.style.display = '';
                    }
                }

                if (data.error) {
                    document.getElementById('pipelineError').textContent = data.error;
                    document.getElementById('pipelineError').classList.remove('hidden');
                    uploadBtn.disabled = false;
                    return;
                }

                if (data.running) {
                    // Continue monitoring
                    setTimeout(checkProgress, 1000);
                } else if (data.progress === 100) {
                    // Pipeline completed successfully
                    setTimeout(() => {
                        document.getElementById('pipelineStatus').classList.add('hidden');
                        createGameBtn.disabled = false;
                        uploadBtn.disabled = true;
                        showPopup('✅ Chat data processed successfully! You can now create your game.');
                    }, 1000);
                }
            })
            .catch(error => {
                console.error('Failed to check pipeline status:', error);
                document.getElementById('pipelineError').textContent = 'Failed to check pipeline status';
                document.getElementById('pipelineError').classList.remove('hidden');
                uploadBtn.disabled = false;
            });
    }

    // Start monitoring
    checkProgress();
}

// Game Creation and Joining
function createGame() {
    const playerName = 'Host'; // You can make this configurable

    // Emit create game event to server
    socket.emit('create_game', { player_name: playerName });
}

function joinGame() {
    const username = document.getElementById('joinUsername').value.trim();
    const gameCode = document.getElementById('joinGameCode').value.trim().toUpperCase();
    const errorDiv = document.getElementById('joinError');

    if (!username) {
        showError(errorDiv, 'Please enter a username');
        return;
    }

    if (!gameCode || gameCode.length < 4) {
        showError(errorDiv, 'Please enter a valid game code');
        return;
    }

    // Emit join game event to server
    socket.emit('join_game', {
        game_code: gameCode,
        player_name: username
    });
}

// Socket.IO Event Handlers
socket.on('game_created', (data) => {
    gameState.isHost = true;
    gameState.roomCode = data.game_code;
    gameState.playerName = data.player_name;
    if (data.host_token) {
        localStorage.setItem('host_token', data.host_token);
    }
    document.getElementById('roomCode').textContent = data.game_code;
    fetchGameDataAndStart();
    showScreen('lobbyHost');
});

socket.on('joined_game', (data) => {
    gameState.isHost = false;
    gameState.playerName = data.player_name;
    gameState.roomCode = data.game_code;
    // Store player_token for reconnection
    if (data.player_token) {
        localStorage.setItem('player_token', data.player_token);
        localStorage.setItem('player_name', data.player_name);
        localStorage.setItem('game_code', data.game_code);
    }
    document.getElementById('playerRoomCode').textContent = data.game_code;
    document.getElementById('playerName').textContent = data.player_name;
    fetchGameDataAndStart();
    showScreen('lobbyPlayer');
});

socket.on('player_joined', (data) => {
    if (gameState.isHost) {
        // Update the entire players list from server data
        gameState.players = data.players;

        // Initialize scores for new players
        data.players.forEach(playerName => {
            if (!gameState.scores[playerName]) {
                gameState.scores[playerName] = 0;
            }
        });

        updatePlayersList();

        // Enable start button if there's at least 1 player
        const startBtn = document.getElementById('startGameBtn');
        if (gameState.players.length >= 1) {
            startBtn.disabled = false;
        }
    }
});

socket.on('player_left', (data) => {
    if (gameState.isHost) {
        // Update the players list from server data
        gameState.players = data.players;
        updatePlayersList();

        // Disable start button if no players
        const startBtn = document.getElementById('startGameBtn');
        if (data.players_count < 1) {
            startBtn.disabled = true;
        }
    }
});

socket.on('game_started', (data) => {
    console.log('Game started event received:', data);
    showScreen('tutorialScreen');
    window.tutorialActive = true;
    window.bufferedQuestionData = null;
    let countdown = 7;
    const countdownElem = document.getElementById('tutorialCountdown');
    if (countdownElem) {
        countdownElem.textContent = `Starting in ${countdown}...`;
    }
    window.tutorialAutoAdvanceTimer = setInterval(() => {
        countdown--;
        if (countdownElem) {
            countdownElem.textContent = `Starting in ${countdown}...`;
        }
        if (countdown <= 0) {
            clearInterval(window.tutorialAutoAdvanceTimer);
            window.tutorialAutoAdvanceTimer = null;
            window.tutorialActive = false;
            showScreen('gameScreen');
            if (window.bufferedQuestionData) {
                handleQuestionEvent(window.bufferedQuestionData);
                window.bufferedQuestionData = null;
            } else if (!gameState.isHost) {
                if (!document.getElementById('currentRound').textContent || document.getElementById('currentRound').textContent === '0') {
                    socket.emit('request_first_question');
                }
            }
        }
    }, 1000);
});

socket.on('timer_failed', () => {
    console.log('Server timer failed, requesting first question...');
    socket.emit('request_first_question');
});

// Listen for host_question and player_question events (replace new_question)
socket.on('host_question', (data) => {
    if (window.tutorialActive) {
        window.bufferedQuestionData = data;
    } else {
        handleQuestionEvent(data);
    }
});
socket.on('player_question', (data) => {
    if (window.tutorialActive) {
        window.bufferedQuestionData = data;
    } else {
        handleQuestionEvent(data);
    }
});

function handleQuestionEvent(data) {
    console.log('Question received:', data);
    showScreen('gameScreen');
    document.getElementById('currentRound').textContent = data.question_number;
    document.getElementById('totalRounds').textContent = data.total_questions;
    const phaseIndicator = document.getElementById('phaseIndicator');
    if (data.phase === 'generated') {
        phaseIndicator.textContent = 'Synthetic Messages';
        phaseIndicator.className = 'phase-indicator synthetic';
        gameState.phase = 'generated';
    } else {
        phaseIndicator.textContent = 'Real Messages';
        phaseIndicator.className = 'phase-indicator real';
        gameState.phase = 'real';
    }
    if (gameState.isHost) {
        document.getElementById('messageText').textContent = `"${data.message}"`;
    } else {
        document.getElementById('messageText').textContent = '';
    }
    const choicesContainer = document.getElementById('choices');
    choicesContainer.innerHTML = '';
    data.options.forEach((option, index) => {
        const button = document.createElement('button');
        button.className = 'choice-btn';
        button.textContent = option;
        button.onclick = () => selectAnswer(option, button);
        choicesContainer.appendChild(button);
    });
    startTimer();
    document.getElementById('distinctivenessScore').classList.add('hidden');
}

socket.on('question_results', (data) => {
    clearInterval(gameState.timer);
    // Show correct/incorrect answers
    document.querySelectorAll('.choice-btn').forEach(btn => {
        btn.disabled = true;
        if (btn.textContent === data.correct_answer) {
            btn.classList.add('correct');
        } else if (btn.textContent === gameState.selectedAnswer && btn.textContent !== data.correct_answer) {
            btn.classList.add('incorrect');
        }
    });
    // Update phase in gameState
    gameState.phase = data.phase;
    // Show results screen
    showRoundResults(data);
});

socket.on('game_finished', (data) => {
    gameState.scores = {};
    data.leaderboard.forEach(player => {
        gameState.scores[player.name] = player.score;
    });
    showFinalResults();
});

socket.on('error', (data) => {
    const errorDiv = document.getElementById('joinError');
    showError(errorDiv, data.message);
});

socket.on('redirect_homepage', () => {
    showHomepage();
});

function generateRoomCode() {
    return Math.random().toString(36).substring(2, 6).toUpperCase();
}

function updatePlayersList() {
    const hostList = document.getElementById('playersList');
    const playerList = document.getElementById('playersListPlayer');

    const playersHtml = gameState.players.map(player =>
        `<div class="player-card">${player}</div>`
    ).join('');

    if (hostList) hostList.innerHTML = playersHtml;
    if (playerList) playerList.innerHTML = playersHtml;
}

function cancelGame() {
    localStorage.removeItem('host_token');
    showHomepage();
}

// Game Logic
function startGame() {
    if (gameState.isHost) {
        socket.emit('start_game');
    }
}

// Listen for all_players_ready event (host only)
socket.on('all_players_ready', () => {
    // Host should advance to next round
    socket.emit('next_round');
});

function updateScoreboard(elementId) {
    const scoreboard = document.getElementById(elementId);
    const sortedPlayers = Object.entries(gameState.scores)
        .sort(([, a], [, b]) => b - a);

    const scoresHtml = sortedPlayers.map(([player, score], index) => {
        const isCurrentPlayer = !gameState.isHost && player === gameState.playerName;
        const rankSymbol = index === 0 ? '<span class="emoji">🏆</span>' : index === 1 ? '<span class="emoji">🥈</span>' : index === 2 ? '<span class="emoji">🥉</span>' : (index + 1);

        return `
            <div class="score-item ${isCurrentPlayer ? 'highlight' : ''}">
                <div class="rank">${rankSymbol}</div>
                <div class="player-name">${player}</div>
                <div class="points">${score} pts</div>
            </div>
        `;
    }).join('');

    scoreboard.innerHTML = scoresHtml;
}

function showFinalResults() {
    showScreen('finalResults');
    const sortedPlayers = Object.entries(gameState.scores)
        .sort(([, a], [, b]) => b - a);
    // Set leaderboard title only
    document.getElementById('winner').textContent = 'Leaderboard';
    updateScoreboard('finalScoreboard');
    // Superlatives: generate from stats
    const superlativesDiv = document.getElementById('superlatives');
    superlativesDiv.innerHTML = '';
    if (gameState.gameData && gameState.gameData.stats) {
        const stats = gameState.gameData.stats;
        const lines = [];
        // Fun, playful superlatives with emojis
        if (stats.most_messages_sent) {
            lines.push(`💬 The <b>Chatty Kathy</b> of the group was <span class='superlative-username'>${stats.most_messages_sent.username}</span> with <b>${stats.most_messages_sent.count}</b> messages sent!`);
        }
        if (stats.longest_messages) {
            lines.push(`📏 <span class='superlative-username'>${stats.longest_messages.username}</span> wrote the <b>longest messages</b>, averaging <b>${stats.longest_messages.average}</b> words per message!`);
        }
        if (stats.user_common_words) {
            for (const [user, words] of Object.entries(stats.user_common_words)) {
                if (words.length > 0) {
                    const top = words[0];
                    lines.push(`🔤 <span class='superlative-username'>${user}</span>'s most-used word was <b>"${top.word}"</b> (<b>${top.count}</b> times)!`);
                }
            }
        }
        if (stats.user_signature_words) {
            for (const [user, words] of Object.entries(stats.user_signature_words)) {
                if (words.length > 0) {
                    const top = words[0];
                    lines.push(`🏷️ <span class='superlative-username'>${user}</span>'s signature word was <b>"${top.word}"</b> (score: <b>${top.score}</b>)!`);
                }
            }
        }
        if (stats.user_signature_phrases) {
            for (const [user, phraseObj] of Object.entries(stats.user_signature_phrases)) {
                if (phraseObj && phraseObj.phrase) {
                    lines.push(`🗣️ <span class='superlative-username'>${user}</span>'s catchphrase: <b>"${phraseObj.phrase}"</b> (<b>${phraseObj.count}</b> times)!`);
                }
            }
        }
        if (stats.most_sentence_capitalizations) {
            lines.push(`🆙 <span class='superlative-username'>${stats.most_sentence_capitalizations.username}</span> capitalized the most sentences (<b>${Math.round(stats.most_sentence_capitalizations.ratio * 100)}%</b>)!`);
        }
        if (stats.capitalization_stats) {
            // Do not show per-user capitalization, only the 'most' below
        }
        if (stats.proper_punctuation) {
            lines.push(`‼️ The <b>Punctuation Pro</b> is <span class='superlative-username'>${stats.proper_punctuation.username}</span> (<b>${Math.round(stats.proper_punctuation.ratio * 100)}%</b> of sentences)!`);
        }
        if (stats.most_exclamation_marks) {
            lines.push(`❗ The <b>Exclamation Enthusiast</b>: <span class='superlative-username'>${stats.most_exclamation_marks.username}</span> with <b>${stats.most_exclamation_marks.count}</b> exclamation marks!`);
        }
        if (stats.most_question_marks) {
            lines.push(`❓ The <b>Curious Cat</b>: <span class='superlative-username'>${stats.most_question_marks.username}</span> with <b>${stats.most_question_marks.count}</b> question marks!`);
        }
        // New format: separate emoji and text
        superlativesDiv.innerHTML = lines.map(line => {
            // Extract emoji (assume it's the first grapheme/character)
            const emojiMatch = line.match(/^([\p{Emoji}\p{So}\p{S}\p{P}]{1,2})\s*/u);
            let emoji = '';
            let text = line;
            if (emojiMatch) {
                emoji = emojiMatch[1];
                text = line.slice(emojiMatch[0].length);
            }
            return `<div class="superlative-item"><span class="emoji">${emoji}</span><span class="text">${text}</span></div>`;
        }).join('');
        superlativesDiv.classList.remove('hidden');
    } else {
        superlativesDiv.classList.add('hidden');
    }
}

function playAgain() {
    gameState.currentRound = 0;
    gameState.answers = {};
    Object.keys(gameState.scores).forEach(player => {
        gameState.scores[player] = 0;
    });
    startGame();
}

function showToast(message, type = 'success') {
    // Remove any existing toast
    const existingToast = document.querySelector('.toast');
    if (existingToast) {
        existingToast.remove();
    }

    // Create new toast
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    // Show toast with animation
    setTimeout(() => {
        toast.classList.add('show');
    }, 100);

    // Hide and remove toast after 2 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }, 2000);
}

function showPopup(message) {
    const popup = document.getElementById('popup');
    if (!popup) return;
    popup.textContent = message;
    popup.style.display = 'block';
    setTimeout(() => {
        popup.style.display = 'none';
    }, 2000);
}

function shareResults() {
    const sortedPlayers = Object.entries(gameState.scores)
        .sort(([, a], [, b]) => b - a);

    const results = sortedPlayers.map(([player, score], index) => {
        const medals = ['🥇', '🥈', '🥉'];
        const medal = medals[index] || '🏅';
        return `${medal} ${player}: ${score} points`;
    }).join('\n');

    const now = new Date();
    const day = now.getDate();
    const month = now.toLocaleString('default', { month: 'long' });
    const year = now.getFullYear();
    const shareText = `I played 🎮 TalkTagger on ${day} ${month} ${year}, and here are the results!\n\n${results}\n\nCheck out nilatabey.com`;

    if (navigator.share) {
        navigator.share({
            title: 'TalkTagger Results',
            text: shareText
        });
    } else if (navigator.clipboard) {
        navigator.clipboard.writeText(shareText).then(() => {
            showPopup('Results copied to clipboard!');
        }).catch(() => {
            showPopup('Failed to copy results');
        });
    } else {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = shareText;
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            showPopup('Results copied to clipboard!');
        } catch (err) {
            showPopup('Failed to copy results');
        }
        document.body.removeChild(textArea);
    }
}

// Utility Functions
function showError(element, message) {
    element.textContent = message;
    element.classList.remove('hidden');
    setTimeout(() => {
        element.classList.add('hidden');
    }, 5000);
}

// Initialize the game when the page loads
document.addEventListener('DOMContentLoaded', function () {
    // Clear any existing error messages
    document.querySelectorAll('.error').forEach(error => {
        error.classList.add('hidden');
    });

    // Set up event listeners for Enter key
    document.getElementById('joinUsername').addEventListener('keypress', function (e) {
        if (e.key === 'Enter') {
            document.getElementById('joinGameCode').focus();
        }
    });

    document.getElementById('joinGameCode').addEventListener('keypress', function (e) {
        if (e.key === 'Enter') {
            joinGame();
        }
    });
});

// Help Modal Functions
function showHelp() {
    const helpModal = document.getElementById('helpModal');
    helpModal.classList.remove('hidden');
    document.body.style.overflow = 'hidden'; // Prevent background scrolling
}

function hideHelp() {
    const helpModal = document.getElementById('helpModal');
    helpModal.classList.add('hidden');
    document.body.style.overflow = ''; // Restore scrolling
}

// Close modal when clicking outside of it
document.addEventListener('DOMContentLoaded', function () {
    const helpModal = document.getElementById('helpModal');
    helpModal.addEventListener('click', function (e) {
        if (e.target === helpModal) {
            hideHelp();
        }
    });

    // Close modal with Escape key
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && !helpModal.classList.contains('hidden')) {
            hideHelp();
        }
    });
});

// On socket connect, check for host_token or player_token and emit reconnect events
socket.on('connect', () => {
    console.log('Connected to server');
    const hostToken = localStorage.getItem('host_token');
    if (hostToken) {
        socket.emit('host_reconnect', { host_token: hostToken });
    }
    // Player reconnection
    const playerToken = localStorage.getItem('player_token');
    const playerName = localStorage.getItem('player_name');
    const gameCode = localStorage.getItem('game_code');
    if (playerToken && playerName && gameCode) {
        socket.emit('player_reconnect', {
            player_token: playerToken,
            player_name: playerName,
            game_code: gameCode
        });
    }
});

// On host_reconnected, you may want to log or update UI if needed
socket.on('host_reconnected', (data) => {
    console.log('Host reconnected for game:', data.game_code);
});

// Add CSS for animations (add this to your style.css)
const additionalCSS = `
.countdown-number {
    transition: all 0.3s ease;
}

.choice-btn.selected {
    background-color: #4CAF50;
    color: white;
    border-color: #4CAF50;
}

.choice-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

@keyframes pulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.1); }
    100% { transform: scale(1); }
}
`;

// When creating or joining a game, fetch /game-data and store in gameState.gameData
function fetchGameDataAndStart() {
    fetch('/game-data')
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert('Game data not available. Please upload and process chat data first.');
                return;
            }
            gameState.gameData = data;
            gameState.phase1Index = 0;
            gameState.phase2Index = 0;
            gameState.phase = 'real';
            const rounds1 = data.game_rounds_1 ? data.game_rounds_1.length : 0;
            const rounds2 = data.game_rounds_2 ? data.game_rounds_2.length : 0;
            gameState.totalRounds = rounds1 + rounds2;
        });
}

function selectAnswer(answer, buttonElement) {
    // Disable all choice buttons
    const choiceButtons = document.querySelectorAll('.choice-btn');
    choiceButtons.forEach(btn => {
        btn.disabled = true;
        btn.classList.remove('selected');
    });

    // Highlight selected answer
    buttonElement.classList.add('selected');

    // Submit answer
    socket.emit('submit_answer', { answer: answer });

    console.log('Answer submitted:', answer);
}

let timerInterval;

function startTimer() {
    let timeLeft = 15;
    const timerElement = document.getElementById('timer');

    // Clear any existing timer
    if (timerInterval) {
        clearInterval(timerInterval);
    }

    // Update timer display
    function updateTimer() {
        timerElement.textContent = timeLeft;

        // Change color as time runs out
        if (timeLeft <= 5) {
            timerElement.style.color = '#ff4444';
            timerElement.style.animation = 'pulse 1s infinite';
        } else if (timeLeft <= 10) {
            timerElement.style.color = '#ff8800';
        } else {
            timerElement.style.color = '#333';
            timerElement.style.animation = 'none';
        }
    }

    // Initial update
    updateTimer();

    timerInterval = setInterval(() => {
        timeLeft--;
        updateTimer();

        if (timeLeft <= 0) {
            clearInterval(timerInterval);

            // Auto-submit if no answer selected
            const selectedChoice = document.querySelector('.choice-btn.selected');
            if (!selectedChoice) {
                // No answer selected - submit empty answer or random
                const choices = document.querySelectorAll('.choice-btn');
                if (choices.length > 0) {
                    // Submit random answer
                    const randomChoice = choices[Math.floor(Math.random() * choices.length)];
                    selectAnswer(randomChoice.textContent, randomChoice);
                }
            }
        }
    }, 1000);
}

function showRoundResults(data) {
    showScreen('roundResults');

    const summaryDiv = document.getElementById('roundSummary');
    const roundActions = document.getElementById('roundActions');
    const hostWaitingMsg = document.getElementById('hostWaitingMsg');
    roundActions.innerHTML = '';
    hostWaitingMsg.classList.add('hidden');

    // Host view
    if (data.view === 'host') {
        // Show two-column layout for host
        document.getElementById('hostRoundResultsColumns').style.display = '';
        document.getElementById('playerRoundSummary').style.display = 'none';
        let shortMessage = data.message;
        if (shortMessage.length > 50) {
            shortMessage = shortMessage.slice(0, 50) + '...';
        }
        document.getElementById('roundSummary').innerHTML = `
            <div class=\"message-card\">\n                <h3>Round Summary</h3>\n                <span class=\"talktagger-yellow\"><strong>Message:</strong></span> ${shortMessage}<br>\n                <span class=\"talktagger-yellow\"><strong>Correct Answer:</strong></span> ${data.correct_answer}<br>\n                <span class=\"talktagger-yellow\"><strong>Distinctiveness Score:</strong></span> ${data.distinctiveness_score ?? ''}<br>\n                <span class=\"talktagger-yellow\"><strong>BERT Similarity:</strong></span> ${data.bert_similarity !== undefined && data.bert_similarity !== null ? data.bert_similarity + '%' : ''}\n            </div>\n        `;
        hostWaitingMsg.classList.remove('hidden');
        // Host will auto-advance when all players are ready (handled by socket event)
    } else {
        // Player view: show single column summary
        document.getElementById('hostRoundResultsColumns').style.display = 'none';
        document.getElementById('playerRoundSummary').style.display = '';
        const playerResult = data.results.find(r => r.player_name === gameState.playerName);
        const isCorrect = playerResult ? playerResult.correct : false;
        const selectedAnswer = playerResult ? playerResult.answer : 'No answer';
        let shortMessage = data.message;
        if (shortMessage.length > 50) {
            shortMessage = shortMessage.slice(0, 50) + '...';
        }
        document.getElementById('playerRoundSummary').innerHTML = `
            <div class=\"message-card\">\n                <h3 class=\"${isCorrect ? 'correct-answer-msg' : 'incorrect-answer-msg'}\">${isCorrect ? '✅ Correct!' : '❌ Incorrect...'}</h3>\n                <span class=\"talktagger-yellow\"><strong>Message:</strong></span> ${shortMessage}<br>\n                <span class=\"talktagger-yellow\"><strong>Correct Answer:</strong></span> ${data.correct_answer}<br>\n                <span class=\"talktagger-yellow\"><strong>Your Answer:</strong></span> ${selectedAnswer}<br>\n                <span class=\"talktagger-yellow\"><strong>Points Earned:</strong></span> ${playerResult ? playerResult.points_earned : 0}<br>\n                <span class=\"talktagger-yellow\"><strong>Distinctiveness Score:</strong></span> ${data.distinctiveness_score ?? ''}<br>\n                <span class=\"talktagger-yellow\"><strong>BERT Similarity:</strong></span> ${data.bert_similarity !== undefined && data.bert_similarity !== null ? data.bert_similarity + '%' : ''}\n            </div>\n        `;
        // Show Ready button
        const readyBtn = document.createElement('button');
        readyBtn.className = 'btn green';
        // Determine if this is the last round
        const isLastSyntheticRound = (data.phase === 'generated' && data.standing === 1 && data.leaderboard.length > 0 && gameState.currentRound === gameState.totalRounds);
        if (data.phase === 'generated' && data.leaderboard && data.leaderboard.length > 0 && gameState.currentRound === gameState.totalRounds) {
            readyBtn.textContent = 'View Final Results';
        } else {
            readyBtn.textContent = 'Ready for Next Round';
        }
        readyBtn.onclick = () => {
            readyBtn.disabled = true;
            readyBtn.textContent = 'Waiting...';
            socket.emit('player_ready');
        };
        roundActions.appendChild(readyBtn);
    }

    // Update scoreboard with server data
    const scoreboard = document.getElementById('roundScoreboard');
    const scoresHtml = data.leaderboard.map((player, index) => {
        const isCurrentPlayer = player.name === gameState.playerName;
        const rankSymbol = index === 0 ? '<span class="emoji">🏆</span>' : index === 1 ? '<span class="emoji">🥈</span>' : index === 2 ? '<span class="emoji">🥉</span>' : (index + 1);
        return `
            <div class="score-item ${isCurrentPlayer ? 'highlight' : ''}">
                <div class="rank">${rankSymbol}</div>
                <div class="player-name">${player.name}</div>
                <div class="points">${player.score} pts</div>
            </div>
        `;
    }).join('');
    scoreboard.innerHTML = scoresHtml;
}

// Add handler for phase_transition event
socket.on('phase_transition', (data) => {
    // Show a transition screen or message
    showScreen('phaseTransition');
    const msgElem = document.getElementById('phaseTransitionMessage');
    if (msgElem) {
        msgElem.textContent = data.message || 'Starting next phase!';
    }
    // Optionally, after a short delay, hide the transition and wait for the next question
    setTimeout(() => {
        // Hide transition, wait for next question event from server
        // The server will send the next player_question/host_question event
        // so just wait for that to update the UI
    }, 2000);
});

function selectPlatform(platform) {
    // Remove selected class from all buttons
    document.querySelectorAll('.platform-button').forEach(btn => {
        btn.classList.remove('selected');
    });
    // Add selected class to clicked button
    const selectedButton = document.querySelector(`[data-platform="${platform}"]`);
    if (selectedButton) selectedButton.classList.add('selected');
    // Update hidden radio button
    document.getElementById(platform === 'dc' ? 'discord' : 'whatsapp').checked = true;
    // Update indicator text if present
    const indicator = document.getElementById('selectionIndicator');
    if (indicator) {
        const platformName = platform === 'dc' ? 'Discord' : 'WhatsApp';
        indicator.textContent = `Selected: ${platformName}`;
    }
}
// Optionally initialize selection on page load
if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', function () {
        const checked = document.getElementById('discord').checked ? 'dc' : 'wp';
        selectPlatform(checked);
    });
}