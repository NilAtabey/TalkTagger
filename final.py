'''
TalkTagger Pipeline

TalkTagger - Can you guess who said that?

TalkTagger will be a game built around real text conversations from a friend group (works with 2+ players). Users will upload their group chat history from WhatsApp, Discord, or any messaging platform, and the model will transform it into a game.

The game will begin by showing real messages randomly selected from the chat. Players will have to guess who sent each message. After a few rounds, once participants are warmed up, the game will start generating new text messages based on each person's texting style or personality. Players will guess who the generated message is most likely from, earning points along the way. The player with the highest score will win.

At the end, the game will present fun superlatives, such as:

- The Chatty Kathy of the group is Alex, with 2,000 messages sent.
- Barry and Chris are the most alike, with a 78% similarity in their texting styles.
- and more

The project will involve personality modeling (e.g., topic modeling), sentiment analysis, text generation (using techniques like RNNs or transformer models), and the development of both the game mechanics and UI.
'''

import os
import shutil
import glob

def cleanup_folders(): # cleans any previous game data
    """Empty the convos_after and data folders"""
    folders_to_clean = [
        "backend/convos_after",
        "backend/data"
    ]
    
    for folder in folders_to_clean:
        if os.path.exists(folder):
            for file_path in glob.glob(os.path.join(folder, "*")):
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        print(f"Removed file: {file_path}")
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                        print(f"Removed directory: {file_path}")
                except Exception as e:
                    print(f"Error removing {file_path}: {e}")
        else: # create folder if it doesn't exist
            os.makedirs(folder)
            print(f"Created folder: {folder}")
    
    print("Cleanup completed!")

# run cleanup before starting the pipeline
cleanup_folders()

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

# get upload_tag from environment variable (set by backend)
# by default set to 'dc'
upload_tag = os.environ.get("UPLOAD_TAG", "dc")

# Step 1: Parse the chat data
if upload_tag == "dc":
    from backend.dc_parser import parse_discord_folder
    parse_discord_folder("backend/convos_before", "backend/convos_after/parsed_discord")
elif upload_tag == "wp":
    from backend.wp_parser import parse_whatsapp_folder
    parse_whatsapp_folder("backend/convos_before", "backend/convos_after/parsed_whatsapp")
else:
    raise ValueError(f"Unknown upload_tag: {upload_tag}")

# Step 2: Create user profiles
if upload_tag == "dc":
    csv_path = "backend/convos_after/parsed_discord.csv"
elif upload_tag == "wp":
    csv_path = "backend/convos_after/parsed_whatsapp.csv"

# Step 3: Create game data
from backend.chat_preprocessor import ChatPreprocessor

preprocessor = ChatPreprocessor()
profiles = preprocessor.process_chat_csv(
    input_csv_path=csv_path,
    output_json_path="backend/data/user_profiles.json"
)
print("Profiles created")

from backend.message_selector import create_talktagger_game_data

game_data = create_talktagger_game_data(
    profiles_path="backend/data/user_profiles.json",
    csv_path=csv_path, 
    output_path="backend/data/real_data.json"
)
print("Real data created")

# Step 4: Generate synthetic messages
from backend.message_generator import generate_improved_synthetic_messages

synthetic_data = generate_improved_synthetic_messages(
    profiles_path="backend/data/user_profiles.json",
    game_data_path="backend/data/real_data.json", 
    output_path="backend/data/synthetic_data.json",
    messages_per_user=5,
    synthetic_rounds=5
)
print("Synthetic data created")

# Step 5: Sentiment analysis (currently commented out)
# from backend.sentiment_classifier import add_sentiment_to_talktagger_data
# enhanced_profiles = add_sentiment_to_talktagger_data(
#     profiles_path="backend/data/user_profiles.json",
#     game_data_path="backend/data/real_data.json",
#     synthetic_data_path="backend/data/synthetic_data.json",
#     output_profiles_path="backend/data/user_profiles_with_sentiment.json",
#     output_game_data_path="backend/data/game_data_with_sentiment.json", 
#     output_synthetic_data_path="backend/data/synthetic_data_with_sentiment.json",
# )

# Step 6: Generate superlatives
from backend.superlatives import main as generate_ending_superlatives

try:
    generate_ending_superlatives()
    print("Superlatives generated successfully")
except Exception as e:
    print(f"Error generating superlatives: {e}")

# Pipeline Complete
print("\n" + "="*60)
print("TALKTAGGER PIPELINE COMPLETE!")
print("="*60)