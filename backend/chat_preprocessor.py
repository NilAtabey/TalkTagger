import os
import re
import json
import pandas as pd
from collections import Counter, defaultdict
from typing import Dict, List
import spacy
from sklearn.feature_extraction.text import CountVectorizer


class ChatPreprocessor:
    """
    Processes parsed chat CSV files (discord, whatsapp, etc.)
    Builds detailed user profiles capturing behavioral and linguistic traits.
    """

    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])
        self.emoji_pattern = re.compile(r":[a-z_]+:")

    def clean_token(self, token):
        return (
            token.lemma_.lower()
            if not token.is_stop and token.is_alpha and len(token.text) > 2
            else None
        )

    def tokenize_user_messages(self, messages: List[str]) -> List[str]:
        tokens = []
        for doc in self.nlp.pipe(messages, batch_size=50):
            tokens.extend([
                self.clean_token(token) for token in doc if self.clean_token(token)
            ])
        return tokens

    def extract_signature_phrases(self, messages: List[str], top_n: int = 5) -> List[Dict[str, int]]:
        # Pre-clean each message using spaCy
        cleaned_msgs = [
            " ".join([
                token.lemma_.lower()
                for token in self.nlp(msg)
                if token.is_alpha and not token.is_stop and len(token.text) > 2
            ])
            for msg in messages if msg.strip()
        ]

        # Extract n-grams
        vectorizer = CountVectorizer(ngram_range=(2, 3), min_df=2, max_features=50)
        X = vectorizer.fit_transform(cleaned_msgs)
        counts = X.sum(axis=0).A1
        phrases = vectorizer.get_feature_names_out()

        phrase_freq = sorted(zip(phrases, counts), key=lambda x: x[1], reverse=True)
        return [{"phrase": p, "count": int(c)} for p, c in phrase_freq[:top_n]]

    def load_csv(self, filepath: str) -> pd.DataFrame:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"CSV file not found: {filepath}")
        df = pd.read_csv(filepath, usecols=[0, 1], names=["author", "cleaned_content"], header=0)
        df.dropna(subset=["author", "cleaned_content"], inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    def _build_user_profiles(self, df: pd.DataFrame) -> Dict[str, Dict]:
        profiles = {}
        all_tokens = defaultdict(list)

        for author in df["author"].unique():
            user_msgs = df[df["author"] == author]["cleaned_content"].dropna().tolist()
            if not user_msgs:
                continue
            tokens = self.tokenize_user_messages(user_msgs)
            all_tokens[author] = tokens

        all_usernames = list(all_tokens.keys())
        global_counts = Counter()
        for user in all_usernames:
            global_counts.update(all_tokens[user])

        for user in all_usernames:
            tokens = all_tokens[user]
            vocab = Counter(tokens)
            msg_count = len(df[df["author"] == user])
            total_word_count = sum(len(msg.split()) for msg in df[df["author"] == user]["cleaned_content"])
            avg_msg_length = total_word_count / msg_count if msg_count else 0
            avg_word_length = sum(len(t) for t in tokens) / len(tokens) if tokens else 0

            signature_scores = {
                word: round(count / (global_counts[word] - count + 1), 3)
                for word, count in vocab.items()
                if count >= 3
            }
            signature_words = sorted(
                signature_scores.items(), key=lambda x: x[1], reverse=True
            )[:10]

            msgs = df[df["author"] == user]["cleaned_content"]
            capitalized_starts = sum(1 for msg in msgs if msg.strip() and msg.strip()[0].isupper())
            lowercase_only = sum(1 for msg in msgs if msg.strip().islower())
            proper_punctuation = sum(1 for msg in msgs if msg.strip()[-1:] in [".", "!", "?"])
            all_caps_word_count = sum(sum(1 for w in msg.split() if w.isupper() and len(w) > 1) for msg in msgs)
            exclam_count = sum(msg.count("!") for msg in msgs)
            question_count = sum(msg.count("?") for msg in msgs)
            emoji_count = sum(len(self.emoji_pattern.findall(msg)) for msg in msgs)

            # 🔥 Signature phrases added here
            signature_phrases = self.extract_signature_phrases(msgs.tolist(), top_n=5)

            profiles[user] = {
                "message_count": msg_count,
                "total_words": total_word_count,
                "avg_message_length_words": round(avg_msg_length, 2),
                "avg_word_length": round(avg_word_length, 2),
                "raw_vocab_size": len(vocab),
                "most_common_words": [{"word": w, "count": c} for w, c in vocab.most_common(10)],
                "signature_words": [{"word": w, "score": s} for w, s in signature_words],
                "signature_phrases": signature_phrases,
                "capitalized_sentence_start_ratio": round(capitalized_starts / msg_count, 3),
                "lowercase_only_message_ratio": round(lowercase_only / msg_count, 3),
                "all_caps_word_ratio": round(all_caps_word_count / total_word_count, 3) if total_word_count else 0,
                "proper_punctuation_ratio": round(proper_punctuation / msg_count, 3),
                "exclamation_count": exclam_count,
                "question_mark_count": question_count,
                "emoji_count": emoji_count,
                "sample_messages": msgs.sample(min(10, msg_count)).tolist(),
            }

        return profiles

    def process_chat_csv(self, input_csv_path: str, output_json_path: str):
        print(f"Loading chat CSV from: {input_csv_path}")
        df = self.load_csv(input_csv_path)

        print("Building user profiles...")
        profiles = self._build_user_profiles(df)

        print(f"Saving user profiles JSON to: {output_json_path}")
        os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(profiles, f, indent=2, ensure_ascii=False)

        print(f"Done! Processed {len(profiles)} users.")
        return profiles