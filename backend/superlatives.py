import json
import random
import re
from typing import Dict, List, Tuple
from collections import Counter
import pandas as pd
from pathlib import Path

def load_json_file(file_path):
    """Load and return JSON data from a file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json_file(data, file_path):
    """Save data to a JSON file with pretty printing."""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_game_rounds_combined():
    """Return a single combined list of real and synthetic game rounds (real first)."""
    real_data = load_json_file('backend/data/real_data.json')
    synthetic_data = load_json_file('backend/data/synthetic_data.json')
    game_rounds_real = real_data.get('game_rounds', [])
    game_rounds_synth = synthetic_data.get('game_rounds', [])
    # Ensure is_synthetic is set
    for q in game_rounds_real:
        q['is_synthetic'] = False
    for q in game_rounds_synth:
        q['is_synthetic'] = True
    return game_rounds_real + game_rounds_synth

def generate_superlatives():
    """Generate superlatives from user profiles and game data."""
    profiles = load_json_file('backend/data/user_profiles.json')
    game_rounds = get_game_rounds_combined()

    superlatives = {
        'game_rounds': game_rounds,
        'stats': {
            'most_messages_sent': {
                'username': max(profiles.items(), key=lambda x: x[1]['message_count'])[0],
                'count': max(profiles.items(), key=lambda x: x[1]['message_count'])[1]['message_count']
            },
            'most_words_said': {
                'username': max(profiles.items(), key=lambda x: x[1]['total_words'])[0],
                'count': max(profiles.items(), key=lambda x: x[1]['total_words'])[1]['total_words']
            },
            'longest_messages': {
                'username': max(profiles.items(), key=lambda x: x[1]['avg_message_length_words'])[0],
                'average': max(profiles.items(), key=lambda x: x[1]['avg_message_length_words'])[1]['avg_message_length_words']
            },
            'user_common_words': {
                username: profile['most_common_words'][:3] 
                for username, profile in profiles.items()
            },
            'user_signature_words': {
                username: profile['signature_words'][:2]
                for username, profile in profiles.items()
            },
            'user_signature_phrases': {
                username: profile['signature_phrases'][0] if profile['signature_phrases'] else None
                for username, profile in profiles.items()
            },
            'capitalization_stats': {
                username: profile['capitalized_sentence_start_ratio']
                for username, profile in profiles.items()
            },
            'proper_punctuation': {
                'username': max(profiles.items(), key=lambda x: x[1]['proper_punctuation_ratio'])[0],
                'ratio': max(profiles.items(), key=lambda x: x[1]['proper_punctuation_ratio'])[1]['proper_punctuation_ratio']
            },
            'most_exclamation_marks': {
                'username': max(profiles.items(), key=lambda x: x[1]['exclamation_count'])[0],
                'count': max(profiles.items(), key=lambda x: x[1]['exclamation_count'])[1]['exclamation_count']
            },
            'most_question_marks': {
                'username': max(profiles.items(), key=lambda x: x[1]['question_mark_count'])[0],
                'count': max(profiles.items(), key=lambda x: x[1]['question_mark_count'])[1]['question_mark_count']
            },
            'most_sentence_capitalizations': {
                'username': max(profiles.items(), key=lambda x: x[1]['capitalized_sentence_start_ratio'])[0],
                'ratio': max(profiles.items(), key=lambda x: x[1]['capitalized_sentence_start_ratio'])[1]['capitalized_sentence_start_ratio']
            }
        }
    }
    return superlatives

def main():
    """Main function to generate and save superlatives."""
    superlatives = generate_superlatives()
    save_json_file(superlatives, 'backend/data/game_data.json')

if __name__ == '__main__':
    main()