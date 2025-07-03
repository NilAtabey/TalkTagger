import json
import random
import re
from typing import Dict, List, Tuple
from collections import Counter
import pandas as pd
from backend.bert_similarity import average_profile_embedding, get_embedding, cosine_similarity


class GameMessageSelector:
    """
    Selects the most characteristic messages from user profiles for TalkTagger gameplay.
    Focuses on messages that best showcase each user's unique texting patterns.
    """
    
    def __init__(self):
        self.emoji_pattern = re.compile(r":[a-z_]+:")
        
    def load_profiles(self, profiles_path: str) -> Dict:
        """Load user profiles from JSON file."""
        with open(profiles_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def load_original_csv(self, csv_path: str) -> pd.DataFrame:
        """Load original parsed CSV to get all messages."""
        return pd.read_csv(csv_path)
    
    def score_message_distinctiveness(self, message: str, user: str, profiles: Dict, all_messages: pd.DataFrame) -> float:
        """
        Score how distinctive a message is for a particular user.
        Higher scores indicate more characteristic messages.
        """
        score = 0.0
        user_profile = profiles[user]
        
        # 1. Signature word bonus (heavily weighted)
        signature_words = [item['word'] for item in user_profile.get('signature_words', [])]
        message_words = message.lower().split()
        signature_matches = sum(1 for word in message_words if word in signature_words)
        score += signature_matches * 3.0
        
        # 2. Signature phrase bonus (very heavily weighted)
        signature_phrases = [item['phrase'] for item in user_profile.get('signature_phrases', [])]
        for phrase in signature_phrases:
            if phrase in message.lower():
                score += 5.0
        
        # 3. Length characteristics
        msg_word_count = len(message_words)
        avg_length = user_profile.get('avg_message_length_words', 0)
        if avg_length > 0:
            # Bonus if message length is typical for this user
            length_ratio = min(msg_word_count, avg_length) / max(msg_word_count, avg_length)
            score += length_ratio * 1.5
        
        # 4. Style pattern bonuses
        # Capitalization patterns
        if message.strip() and message.strip()[0].isupper():
            cap_ratio = user_profile.get('capitalized_sentence_start_ratio', 0)
            score += cap_ratio * 2.0
        
        if message.islower():
            lowercase_ratio = user_profile.get('lowercase_only_message_ratio', 0)
            score += lowercase_ratio * 2.0
        
        # Punctuation patterns
        if message.strip() and message.strip()[-1] in '.!?':
            punct_ratio = user_profile.get('proper_punctuation_ratio', 0)
            score += punct_ratio * 1.5
        
        # Exclamation usage
        exclamation_count = message.count('!')
        if exclamation_count > 0:
            user_exclamation_freq = user_profile.get('exclamation_count', 0) / user_profile.get('message_count', 1)
            score += exclamation_count * user_exclamation_freq * 2.0
        
        # Question usage
        question_count = message.count('?')
        if question_count > 0:
            user_question_freq = user_profile.get('question_mark_count', 0) / user_profile.get('message_count', 1)
            score += question_count * user_question_freq * 2.0
        
        # All caps words
        caps_words = sum(1 for word in message_words if word.isupper() and len(word) > 1)
        if caps_words > 0:
            caps_ratio = user_profile.get('all_caps_word_ratio', 0)
            score += caps_words * caps_ratio * 2.0
        
        # Emoji usage
        emoji_count = len(self.emoji_pattern.findall(message))
        if emoji_count > 0:
            user_emoji_freq = user_profile.get('emoji_count', 0) / user_profile.get('message_count', 1)
            score += emoji_count * user_emoji_freq * 2.0
        
        # 5. Common words penalty (reduce score for messages with only common words)
        user_common_words = [item['word'] for item in user_profile.get('most_common_words', [])]
        common_word_matches = sum(1 for word in message_words if word.lower() in user_common_words)
        if len(message_words) > 0:
            common_ratio = common_word_matches / len(message_words)
            if common_ratio > 0.8:  # Too generic
                score *= 0.5
        
        return score
    
    def filter_suitable_messages(self, messages: List[str]) -> List[str]:
        """Filter out messages that aren't suitable for gameplay."""
        filtered = []
        
        for msg in messages:
            msg = msg.strip()
            
            # Skip empty or very short messages
            if len(msg) < 5:
                continue
                
            # Skip URLs
            if 'http' in msg.lower() or 'www.' in msg.lower():
                continue
                
            # Skip messages that are mostly numbers/dates
            if re.match(r'^[\d\s\-\/\.,:]+$', msg):
                continue
                
            # Skip very long messages (hard to guess from)
            if len(msg.split()) > 50:
                continue
                
            # Skip messages with too many special characters
            special_char_ratio = sum(1 for c in msg if not c.isalnum() and c not in ' .,!?-\'') / len(msg)
            if special_char_ratio > 0.3:
                continue
                
            filtered.append(msg)
        
        return filtered
    
    def select_game_messages(self, profiles: Dict, original_csv_path: str, 
                           messages_per_user: int = 10, min_score_threshold: float = 1.0) -> Dict:
        """
        Select the most characteristic messages for each user for gameplay.
        
        Args:
            profiles: User profiles dictionary
            original_csv_path: Path to original parsed CSV
            messages_per_user: Number of messages to select per user
            min_score_threshold: Minimum distinctiveness score required
            
        Returns:
            Dictionary with selected messages for each user
        """
        # Load all messages
        df = self.load_original_csv(original_csv_path)
        
        selected_messages = {}
        
        # Compute average profile embeddings for each user
        user_profile_embeddings = {}
        for user in profiles.keys():
            # Get all messages from this user
            user_messages = df[df['author'] == user]['content'].dropna().tolist()
            if user_messages:
                user_profile_embeddings[user] = average_profile_embedding(user_messages)
            else:
                user_profile_embeddings[user] = None
        
        for user in profiles.keys():
            print(f"Selecting messages for {user}...")
            
            # Get all messages from this user
            user_messages = df[df['author'] == user]['content'].dropna().tolist()
            
            # DM name filtering: if only 2 participants, filter out messages mentioning any part of either name
            if len(profiles) == 2:
                # Get all name parts (split on space and punctuation)
                name_parts = set()
                for participant in profiles.keys():
                    # Split on non-word characters (space, dot, etc.)
                    parts = re.split(r'\W+', participant.lower())
                    name_parts.update([p for p in parts if p])
                # Remove messages mentioning any name part
                user_messages = [msg for msg in user_messages if not any(part in msg.lower() for part in name_parts)]
            
            # Filter out unsuitable messages
            suitable_messages = self.filter_suitable_messages(user_messages)
            
            if len(suitable_messages) < 5:
                print(f"Warning: Only {len(suitable_messages)} suitable messages found for {user}")
            
            # Score each message
            message_scores = []
            for msg in suitable_messages:
                score = self.score_message_distinctiveness(msg, user, profiles, df)
                if score >= min_score_threshold:
                    message_scores.append((msg, score))
            
            # Sort by score (highest first) and select top messages
            message_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Select messages, ensuring variety
            selected = []
            used_words = set()
            
            for msg, score in message_scores:
                if len(selected) >= messages_per_user:
                    break
                
                # Avoid too similar messages
                msg_words = set(msg.lower().split())
                overlap = len(msg_words.intersection(used_words))
                
                if overlap < len(msg_words) * 0.7:  # Less than 70% word overlap
                    # Compute BERT similarity (as percentage)
                    profile_emb = user_profile_embeddings[user]
                    if profile_emb is not None:
                        msg_emb = get_embedding(msg)
                        bert_sim = cosine_similarity([profile_emb], [msg_emb])[0][0] * 100
                        bert_sim = round(bert_sim, 1)
                    else:
                        bert_sim = None
                    selected.append({
                        'message': msg,
                        'distinctiveness_score': round(score, 2),
                        'bert_similarity': bert_sim,
                        'is_synthetic': False
                    })
                    used_words.update(msg_words)
            
            selected_messages[user] = selected
            print(f"Selected {len(selected)} messages for {user}")
        
        return selected_messages
    
    def create_game_rounds(self, selected_messages: Dict, rounds: int = 5) -> List[Dict]:
        """
        Create game rounds by randomly selecting messages from different users.
        
        Args:
            selected_messages: Dictionary of selected messages per user
            rounds: Number of game rounds to create
            
        Returns:
            List of game round dictionaries
        """
        game_rounds = []
        all_users = list(selected_messages.keys())
        
        # Collect all messages with their authors
        all_game_messages = []
        for user, messages in selected_messages.items():
            for msg_data in messages:
                all_game_messages.append({
                    'author': user,
                    'message': msg_data['message'],
                    'score': msg_data['distinctiveness_score'],
                    'bert_similarity': msg_data['bert_similarity']
                })
        
        # Shuffle and select for rounds
        random.shuffle(all_game_messages)
        
        for i in range(min(rounds, len(all_game_messages))):
            msg_data = all_game_messages[i]
            
            # Create answer choices (correct author + random others)
            choices = [msg_data['author']]
            other_users = [u for u in all_users if u != msg_data['author']]
            choices.extend(random.sample(other_users, min(3, len(other_users))))
            random.shuffle(choices)
            
            game_rounds.append({
                'round': i + 1,
                'message': msg_data['message'],
                'correct_author': msg_data['author'],
                'choices': choices,
                'distinctiveness_score': msg_data['score'],
                'bert_similarity': msg_data['bert_similarity'],
                'is_synthetic': False
            })
        
        return game_rounds
    
    def save_game_data(self, selected_messages: Dict, game_rounds: List[Dict], output_path: str):
        """Save the game data to JSON file."""
        game_data = {
            'selected_messages': selected_messages,
            'game_rounds': game_rounds,
            'metadata': {
                'total_users': len(selected_messages),
                'total_selected_messages': sum(len(msgs) for msgs in selected_messages.values()),
                'total_game_rounds': len(game_rounds)
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(game_data, f, indent=2, ensure_ascii=False)
        
        print(f"Game data saved to: {output_path}")
        return game_data


def create_talktagger_game_data(profiles_path: str, csv_path: str, output_path: str, 
                               messages_per_user: int = 20, game_rounds: int = 5):
    """
    Convenience function to create complete TalkTagger game data.
    
    Args:
        profiles_path: Path to user profiles JSON
        csv_path: Path to original parsed CSV
        output_path: Path to save game data
        messages_per_user: Number of characteristic messages per user
        game_rounds: Number of game rounds to create
    """
    selector = GameMessageSelector()
    
    # Load profiles
    print("Loading user profiles...")
    profiles = selector.load_profiles(profiles_path)
    
    # Select characteristic messages
    print("Selecting characteristic messages...")
    selected_messages = selector.select_game_messages(
        profiles, csv_path, messages_per_user
    )
    
    # Create game rounds
    print("Creating game rounds...")
    rounds = selector.create_game_rounds(selected_messages, game_rounds)
    
    # Save everything
    print("Saving game data...")
    game_data = selector.save_game_data(selected_messages, rounds, output_path)
    
    # Print summary
    print("\n" + "="*50)
    print("TalkTagger Game Data Summary")
    print("="*50)
    print(f"Users: {game_data['metadata']['total_users']}")
    print(f"Selected Messages: {game_data['metadata']['total_selected_messages']}")
    print(f"Game Rounds: {game_data['metadata']['total_game_rounds']}")
    
    for user, messages in selected_messages.items():
        avg_score = sum(msg['distinctiveness_score'] for msg in messages) / len(messages)
        print(f"  {user}: {len(messages)} messages (avg score: {avg_score:.2f})")
    
    return game_data