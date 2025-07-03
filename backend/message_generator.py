import json
import requests
import random
import time
from typing import Dict, List, Optional
import importlib.util
import sys
import re
from backend.bert_similarity import average_profile_embedding, get_embedding, cosine_similarity

API_KEY = "" # replace with your own mistral ai api key!

class ImprovedMistralMessageGenerator:
    """
    Enhanced version that generates more balanced messages and calculates distinctiveness scores.
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or API_KEY
        self.api_url = "https://api.mistral.ai/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        self.model_name = "mistral-small-2503"
        self.emoji_pattern = re.compile(r":[a-z_]+:")
        
        # Topics for message generation variety  
        self.conversation_topics = [
            "weekend plans", "food recommendations", "work/school stress", "funny stories",
            "travel experiences", "movie/TV show opinions", "music recommendations", 
            "gaming experiences", "social media posts", "random thoughts", "daily activities",
            "weather complaints", "technology issues", "relationship advice", "hobby discussions"
        ]
    
    def load_data(self, profiles_path: str, game_data_path: str) -> Dict:
        """Load user profiles and game data."""
        with open(profiles_path, 'r', encoding='utf-8') as f:
            profiles = json.load(f)
        
        with open(game_data_path, 'r', encoding='utf-8') as f:
            game_data = json.load(f)
        
        return profiles, game_data
    
    def create_balanced_user_prompt(self, user: str, profile: Dict, sample_messages: List[str], 
                                   count: int = 5, topics: List[str] = None) -> str:
        """
        Create a more balanced prompt that doesn't make capitalization patterns too obvious.
        """
        # Extract key characteristics
        signature_words = [item['word'] for item in profile.get('signature_words', [])[:5]]
        signature_phrases = [item['phrase'] for item in profile.get('signature_phrases', [])[:3]]
        avg_length = profile.get('avg_message_length_words', 10)
        
        # Style characteristics - but make them more subtle
        caps_ratio = profile.get('capitalized_sentence_start_ratio', 0.5)
        lowercase_ratio = profile.get('lowercase_only_message_ratio', 0)
        punctuation_ratio = profile.get('proper_punctuation_ratio', 0.5)
        exclamation_freq = profile.get('exclamation_count', 0) / profile.get('message_count', 1)
        question_freq = profile.get('question_mark_count', 0) / profile.get('message_count', 1)
        
        # Build more balanced style instructions
        style_instructions = []
        
        # More nuanced capitalization rules
        if lowercase_ratio > 0.6:
            style_instructions.append("- Mostly use lowercase, occasionally capitalize")
        elif caps_ratio > 0.8:
            style_instructions.append("- Usually capitalize sentences properly")
        else:
            style_instructions.append("- Mix capitalized and lowercase naturally")
            
        # More subtle punctuation rules
        if punctuation_ratio < 0.2:
            style_instructions.append("- Often skip punctuation")
        elif punctuation_ratio > 0.8:
            style_instructions.append("- Usually punctuate properly")
        else:
            style_instructions.append("- Sometimes punctuate, sometimes don't")
            
        # Other style elements
        if exclamation_freq > 0.08:
            style_instructions.append("- Use exclamation marks for emphasis")
        if question_freq > 0.05:
            style_instructions.append("- Ask questions when natural")
        
        # Create topic list for variety
        topics_instruction = ""
        if topics:
            topics_instruction = f"Vary topics: {', '.join(topics)}"
        
        prompt = f"""Generate {count} text messages in {user}'s style. Make them realistic and varied.

WRITING PATTERNS FOR {user}:
- Typical length: {avg_length} words
- Key vocabulary: {', '.join(signature_words) if signature_words else 'varied'}
- Common phrases: {', '.join(signature_phrases) if signature_phrases else 'none specific'}

STYLE GUIDELINES:
{chr(10).join(style_instructions)}

EXAMPLE MESSAGES:
{chr(10).join(f'"{msg}"' for msg in sample_messages[:6])}

{topics_instruction}

Create {count} different messages. Each should feel authentic but varied. Format as numbered list:
1. [message]
2. [message]
etc."""

        return prompt
    
    def calculate_synthetic_distinctiveness_score(self, message: str, user: str, profiles: Dict) -> float:
        """
        Calculate distinctiveness score for synthetic messages using same logic as real messages.
        """
        score = 0.0
        user_profile = profiles[user]
        
        # 1. Signature word bonus
        signature_words = [item['word'] for item in user_profile.get('signature_words', [])]
        message_words = message.lower().split()
        signature_matches = sum(1 for word in message_words if word in signature_words)
        score += signature_matches * 3.0
        
        # 2. Signature phrase bonus
        signature_phrases = [item['phrase'] for item in user_profile.get('signature_phrases', [])]
        for phrase in signature_phrases:
            if phrase in message.lower():
                score += 5.0
        
        # 3. Length characteristics
        msg_word_count = len(message_words)
        avg_length = user_profile.get('avg_message_length_words', 0)
        if avg_length > 0:
            length_ratio = min(msg_word_count, avg_length) / max(msg_word_count, avg_length)
            score += length_ratio * 1.5
        
        # 4. Style pattern bonuses
        if message.strip() and message.strip()[0].isupper():
            cap_ratio = user_profile.get('capitalized_sentence_start_ratio', 0)
            score += cap_ratio * 2.0
        
        if message.islower():
            lowercase_ratio = user_profile.get('lowercase_only_message_ratio', 0)
            score += lowercase_ratio * 2.0
        
        if message.strip() and message.strip()[-1] in '.!?':
            punct_ratio = user_profile.get('proper_punctuation_ratio', 0)
            score += punct_ratio * 1.5
        
        exclamation_count = message.count('!')
        if exclamation_count > 0:
            user_exclamation_freq = user_profile.get('exclamation_count', 0) / user_profile.get('message_count', 1)
            score += exclamation_count * user_exclamation_freq * 2.0
        
        question_count = message.count('?')
        if question_count > 0:
            user_question_freq = user_profile.get('question_mark_count', 0) / user_profile.get('message_count', 1)
            score += question_count * user_question_freq * 2.0
        
        caps_words = sum(1 for word in message_words if word.isupper() and len(word) > 1)
        if caps_words > 0:
            caps_ratio = user_profile.get('all_caps_word_ratio', 0)
            score += caps_words * caps_ratio * 2.0
        
        emoji_count = len(self.emoji_pattern.findall(message))
        if emoji_count > 0:
            user_emoji_freq = user_profile.get('emoji_count', 0) / user_profile.get('message_count', 1)
            score += emoji_count * user_emoji_freq * 2.0
        
        # Common words penalty
        user_common_words = [item['word'] for item in user_profile.get('most_common_words', [])]
        common_word_matches = sum(1 for word in message_words if word.lower() in user_common_words)
        if len(message_words) > 0:
            common_ratio = common_word_matches / len(message_words)
            if common_ratio > 0.8:
                score *= 0.5
        
        return score
    
    def parse_batch_response(self, response: str) -> List[str]:
        """Parse the batch response from Mistral API into individual messages."""
        messages = []
        lines = response.strip().split('\n')
        
        current_message = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if re.match(r'^\d+\.\s*', line):
                if current_message.strip():
                    messages.append(current_message.strip())
                current_message = re.sub(r'^\d+\.\s*', '', line)
            else:
                if current_message:
                    current_message += " " + line
                else:
                    current_message = line
        
        if current_message.strip():
            messages.append(current_message.strip())
        
        return messages
    
    def call_mistral_api(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        """Call Mistral API with retry logic and error handling."""
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 400,
            "temperature": 0.85,  # Slightly lower for more consistency
            "top_p": 0.9
        }
        
        for attempt in range(max_retries):
            try:
                response = requests.post(self.api_url, headers=self.headers, json=payload)
                
                if response.status_code == 200:
                    result = response.json()
                    message = result['choices'][0]['message']['content'].strip()
                    return message
                    
                elif response.status_code == 429:
                    wait_time = 2 ** attempt
                    print(f"Rate limited. Waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                    
                else:
                    print(f"API Error {response.status_code}: {response.text}")
                    
            except Exception as e:
                print(f"Request failed (attempt {attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(1)
        
        return None
    
    def generate_messages_for_user(self, user: str, profile: Dict, sample_messages: List[str], 
                                 count: int = 5) -> List[Dict]:
        """
        Generate multiple messages for a specific user with distinctiveness scores.
        Returns list of message dictionaries with scores.
        """
        print(f"Generating {count} messages for {user}...")
        
        topics = random.sample(self.conversation_topics, min(count, len(self.conversation_topics)))
        prompt = self.create_balanced_user_prompt(user, profile, sample_messages, count, topics)
        response = self.call_mistral_api(prompt)
        
        if response:
            generated_messages = self.parse_batch_response(response)
            
            # Calculate distinctiveness scores for each message
            scored_messages = []
            for msg in generated_messages:
                score = self.calculate_synthetic_distinctiveness_score(msg, user, {user: profile})
                scored_messages.append({
                    'message': msg,
                    'distinctiveness_score': round(score, 2),
                    'is_synthetic': True
                })
            
            if scored_messages:
                print(f"  [OK] Generated {len(scored_messages)} messages for {user}")
                for i, msg_data in enumerate(scored_messages):
                    print(f"    {i+1}. [{msg_data['distinctiveness_score']}] {msg_data['message'][:50]}...")
            else:
                print(f"  [ERROR] Failed to parse messages for {user}")
                
            return scored_messages
        else:
            print(f"  [ERROR] API call failed for {user}")
            return []
    
    def generate_all_synthetic_messages(self, profiles: Dict, game_data: Dict, 
                                      messages_per_user: int = 5) -> Dict:
        """
        Generate synthetic messages for all users with consistent scoring.
        """
        all_synthetic_messages = {}
        # Compute average profile embeddings for each user from their real messages
        user_profile_embeddings = {}
        for user in profiles.keys():
            sample_messages = []
            if user in game_data.get('selected_messages', {}):
                sample_messages = [
                    msg['message'] for msg in game_data['selected_messages'][user][:10]
                ]
            if len(sample_messages) < 5:
                sample_messages.extend(profiles[user].get('sample_messages', [])[:10])
            if sample_messages:
                user_profile_embeddings[user] = average_profile_embedding(sample_messages)
            else:
                user_profile_embeddings[user] = None
        for user in profiles.keys():
            print(f"\n{'='*50}")
            print(f"Processing user: {user}")
            print(f"{'='*50}")
            # Get sample messages
            sample_messages = []
            if user in game_data.get('selected_messages', {}):
                sample_messages = [
                    msg['message'] for msg in game_data['selected_messages'][user][:10]
                ]
            if len(sample_messages) < 5:
                sample_messages.extend(profiles[user].get('sample_messages', [])[:10])
            if not sample_messages:
                print(f"[WARNING] No sample messages found for {user}, skipping...")
                continue
            # Generate messages with scores
            synthetic_messages = self.generate_messages_for_user(
                user, profiles[user], sample_messages, messages_per_user
            )
            # Add BERT similarity to each synthetic message
            profile_emb = user_profile_embeddings[user]
            for msg_data in synthetic_messages:
                if profile_emb is not None:
                    msg_emb = get_embedding(msg_data['message'])
                    bert_sim = cosine_similarity([profile_emb], [msg_emb])[0][0] * 100
                    bert_sim = round(bert_sim, 1)
                else:
                    bert_sim = None
                msg_data['bert_similarity'] = bert_sim
            # DM name filtering: if only 2 participants, filter out messages mentioning any part of either name
            if len(profiles) == 2:
                name_parts = set()
                for participant in profiles.keys():
                    parts = re.split(r'\W+', participant.lower())
                    name_parts.update([p for p in parts if p])
                synthetic_messages = [
                    msg for msg in synthetic_messages
                    if not any(part in msg['message'].lower() for part in name_parts)
                ]
            all_synthetic_messages[user] = synthetic_messages
            print(f"Generated {len(synthetic_messages)} scored messages for {user}")
        
        return all_synthetic_messages
    
    def create_synthetic_game_rounds(self, synthetic_messages: Dict, rounds: int = 5) -> List[Dict]:
        """Create game rounds using synthetic messages with consistent format."""
        game_rounds = []
        all_users = list(synthetic_messages.keys())
        
        # Collect all synthetic messages
        all_messages = []
        for user, messages in synthetic_messages.items():
            for msg_data in messages:
                all_messages.append({
                    'author': user,
                    'message': msg_data['message'],
                    'distinctiveness_score': msg_data['distinctiveness_score'],
                    'bert_similarity': msg_data.get('bert_similarity'),
                    'is_synthetic': True
                })
        
        # Shuffle and select for rounds
        random.shuffle(all_messages)
        
        for i in range(min(rounds, len(all_messages))):
            msg_data = all_messages[i]
            
            # Create answer choices
            choices = [msg_data['author']]
            other_users = [u for u in all_users if u != msg_data['author']]
            choices.extend(random.sample(other_users, min(3, len(other_users))))
            random.shuffle(choices)
            
            game_rounds.append({
                'round': i + 1,
                'message': msg_data['message'],
                'correct_author': msg_data['author'],
                'choices': choices,
                'distinctiveness_score': msg_data['distinctiveness_score'],
                'bert_similarity': msg_data.get('bert_similarity'),
                'is_synthetic': True,
            })
        
        return game_rounds
    
    def save_synthetic_data(self, synthetic_messages: Dict, synthetic_rounds: List[Dict], 
                           output_path: str) -> Dict:
        """Save synthetic message data with consistent format."""
        synthetic_data = {
            'selected_messages': synthetic_messages,  # Consistent with game_data format
            'game_rounds': synthetic_rounds,
            'metadata': {
                'total_users': len(synthetic_messages),
                'total_synthetic_messages': sum(len(msgs) for msgs in synthetic_messages.values()),
                'total_game_rounds': len(synthetic_rounds)
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(synthetic_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n[OK] Synthetic data saved to: {output_path}")
        return synthetic_data


def generate_improved_synthetic_messages(profiles_path: str, game_data_path: str, 
                                       output_path: str, messages_per_user: int = 5,
                                       synthetic_rounds: int = 5):
    """
    Generate improved synthetic messages with consistent scoring and balanced style patterns.
    """
    generator = ImprovedMistralMessageGenerator()
    
    # Load data
    print("Loading profiles and game data...")
    profiles, game_data = generator.load_data(profiles_path, game_data_path)
    
    # Generate synthetic messages
    print("Starting improved synthetic message generation...")
    synthetic_messages = generator.generate_all_synthetic_messages(
        profiles, game_data, messages_per_user
    )
    
    # Create synthetic game rounds
    print("Creating synthetic game rounds...")
    rounds = generator.create_synthetic_game_rounds(synthetic_messages, synthetic_rounds)
    
    # Save everything
    synthetic_data = generator.save_synthetic_data(synthetic_messages, rounds, output_path)
    
    # Print summary
    print("\n" + "="*60)
    print("Improved TalkTagger Synthetic Generation Summary")
    print("="*60)
    print(f"Total synthetic messages generated: {synthetic_data['metadata']['total_synthetic_messages']}")
    print(f"Selected synthetic game rounds: {synthetic_data['metadata']['total_game_rounds']}")
    print(f"Total num of users processed: {synthetic_data['metadata']['total_users']}")
    
    for user, messages in synthetic_messages.items():
        avg_score = sum(msg['distinctiveness_score'] for msg in messages) / len(messages) if messages else 0
        print(f"  {user}: {len(messages)} messages generated (avg distinctiveness score: {avg_score:.2f})")
    
    return synthetic_data