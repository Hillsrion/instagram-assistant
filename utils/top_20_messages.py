import os
import re

def get_message_counts(directory):
    conversations = []
    
    # Iterate over all files in the directory
    for filename in os.listdir(directory):
        if filename.endswith(".txt"):
            filepath = os.path.join(directory, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as file:
                    content = file.read()
                    
                    # Search for "Nombre de messages:"
                    match = re.search(r"Nombre de messages:\s*(\d+)", content)
                    if match:
                        count = int(match.group(1))
                        conversations.append({'filename': filename, 'count': count})
            except Exception as e:
                print(f"Error reading file {filename}: {e}")
                
    return conversations

def main():
    directory = "instagram_conversations"
    
    if not os.path.exists(directory):
        print(f"Directory '{directory}' not found.")
        return

    conversations = get_message_counts(directory)
    
    # Sort by count in descending order
    sorted_conversations = sorted(conversations, key=lambda x: x['count'], reverse=True)
    
    # Get top 20
    top_20 = sorted_conversations[:20]
    
    print(f"{'Rank':<5} {'Count':<10} {'Filename'}")
    print("-" * 60)
    
    for rank, conv in enumerate(top_20, 1):
        print(f"{rank:<5} {conv['count']:<10} {conv['filename']}")

if __name__ == "__main__":
    main()
