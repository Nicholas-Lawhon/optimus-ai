from memory.manager import MemoryManager

def check():
    print("🕵️ Checking Database for Tool Patterns...")
    
    # Initialize (connects to the same memory.db)
    manager = MemoryManager.initialize()
    
    # Fetch patterns using the method you just wrote
    patterns = manager.get_tool_patterns()
    
    if not patterns:
        print("❌ No patterns found. Something went wrong.")
    else:
        print(f"✅ Found {len(patterns)} pattern(s)!")
        for p in patterns:
            print(f"   - Tool: {p.metadata.get('tool_name', 'Unknown')}") # We didn't save metadata in the snippet, so this might be empty if we didn't add it to metadata dict
            print(f"   - Content: {p.content}")
            print(f"   - Created: {p.created_at}")

    manager.close()

if __name__ == "__main__":
    check()