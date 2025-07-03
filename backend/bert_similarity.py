from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Load a pre-trained sentence transformer model (do this once)
model = SentenceTransformer('all-MiniLM-L6-v2')

def get_embedding(text):
    return model.encode([text])[0]

def compute_similarity(text1, text2):
    emb1 = get_embedding(text1)
    emb2 = get_embedding(text2)
    return cosine_similarity([emb1], [emb2])[0][0]

def average_profile_embedding(messages):
    embeddings = [get_embedding(msg) for msg in messages]
    return np.mean(embeddings, axis=0)
