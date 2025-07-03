import re
import os
import csv
import json
from datetime import datetime
from typing import List, Dict, Optional, Any

class WhatsAppParser:
    """
    Parses WhatsApp chat exports and converts them to structured format.
    Designed to work as part of the TalkTagger processing chain.
    """
    def __init__(self):
        self.msg_pattern = re.compile(r"^\[(\d{2}/\d{2}/\d{2}), (\d{2}:\d{2}:\d{2})\] (.*?): (.+)")
    
    def parse_single_file(self, input_path: str) -> List[Dict]:
        messages = []
        current_user = None
        current_message = []
        with open(input_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if lines and "Messages and calls are end-to-end encrypted. Only people in this chat can read, listen to, or share them." in lines[0]:
            lines = lines[1:]
        for line in lines:
            line = line.strip()
            line = line.replace('\u200e', '')
            if "POLL:" in line or re.match(r"^\[.*?\] .*?OPTION:", line) or re.match(r"^OPTION:", line):
                continue
            match = self.msg_pattern.match(line)
            if match:
                if current_user and current_message:
                    messages.append(self._create_message_dict(current_user, current_message))
                date, time, user, message = match.groups()
                if any(x in message.lower() for x in ["omitted", "joined", "left", "changed", "created", "removed", "added", "deleted", "this message was deleted", "image omitted", "video omitted", "sticker omitted"]):
                    current_user = None
                    current_message = []
                    continue
                if message == "Voice call." or message == "Video call.":
                    current_user = None
                    current_message = []
                    continue
                message = message.replace('<This message was edited>', '').strip()
                message = re.sub(r'\*\*(.*?)\*\*', r'\1', message)
                message = re.sub(r'\*(.*?)\*', r'\1', message)
                message = re.sub(r'_(.*?)_', r'\1', message)
                message = re.sub(r'~(.*?)~', r'\1', message)
                current_user = user.strip()
                current_message = [message.strip()]
            else:
                if current_user:
                    current_message.append(line)
        if current_user and current_message:
            messages.append(self._create_message_dict(current_user, current_message))
        return messages
    
    def _create_message_dict(self, user: str, message_lines: List[str]) -> Dict:
        content = " ".join(message_lines).strip()
        return {
            "author": user,
            "content": content
        }
    
    def parse_folder(self, input_folder: str, output_format: str = "csv") -> Dict[str, Any]:
        if not os.path.exists(input_folder):
            raise FileNotFoundError(f"Input folder not found: {input_folder}")
        all_messages = []
        processed_files = []
        failed_files = []
        for filename in os.listdir(input_folder):
            if not filename.endswith(".txt"):
                continue
            input_path = os.path.join(input_folder, filename)
            print(f"Processing: {filename}")
            try:
                messages = self.parse_single_file(input_path)
                if messages:
                    all_messages.extend(messages)
                    processed_files.append({
                        "filename": filename,
                        "message_count": len(messages),
                        "users": list(set(msg["author"] for msg in messages))
                    })
                    print(f"[OK] Parsed {len(messages)} messages from {filename}")
                else:
                    failed_files.append(filename)
                    print(f"[WARNING] No messages found in {filename}")
            except Exception as e:
                failed_files.append(filename)
                print(f"[ERROR] Failed to parse {filename}: {str(e)}")
        results = {
            "messages": all_messages,
            "metadata": {
                "total_messages": len(all_messages),
                "processed_files": processed_files,
                "failed_files": failed_files,
                "unique_users": list(set(msg["author"] for msg in all_messages)),
                "parsed_at": datetime.now().isoformat()
            }
        }
        return results
    
    def save_results(self, results: Dict[str, Any], output_path: str, format: str = "csv"):
        messages = results["messages"]
        csv_path = f"{output_path}.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            if messages:
                writer = csv.DictWriter(f, fieldnames=["author", "content"])
                writer.writeheader()
                for msg in messages:
                    writer.writerow({
                        "author": msg["author"],
                        "content": msg["content"]
                    })
                print(f"[OK] Saved CSV: {csv_path}")
    
    def get_parsing_summary(self, results: Dict[str, Any]) -> str:
        metadata = results["metadata"]
        summary = f"""
WhatsApp Chat Parsing Summary
============================
Total Messages: {metadata['total_messages']}
Unique Users: {len(metadata['unique_users'])}
Processed Files: {len(metadata['processed_files'])}
Failed Files: {len(metadata['failed_files'])}

Users: {', '.join(metadata['unique_users'])}

File Details:
"""
        for file_info in metadata['processed_files']:
            summary += f"  - {file_info['filename']}: {file_info['message_count']} messages\n"
        if metadata['failed_files']:
            summary += f"\nFailed Files: {', '.join(metadata['failed_files'])}\n"
        return summary

def parse_whatsapp_folder(input_folder: str, output_path: str = None, output_format: str = "csv") -> Dict[str, Any]:
    parser = WhatsAppParser()
    results = parser.parse_folder(input_folder, output_format)
    if output_path:
        parser.save_results(results, output_path, output_format)
    print(parser.get_parsing_summary(results))
    return results

def parse_whatsapp_file(input_file: str, output_path: str = None) -> Dict[str, Any]:
    parser = WhatsAppParser()
    messages = parser.parse_single_file(input_file)
    results = {
        "messages": messages,
        "metadata": {
            "total_messages": len(messages),
            "unique_users": list(set(msg["author"] for msg in messages)),
            "parsed_at": datetime.now().isoformat(),
            "source_file": input_file
        }
    }
    if output_path:
        parser.save_results(results, output_path, "csv")
    return results
