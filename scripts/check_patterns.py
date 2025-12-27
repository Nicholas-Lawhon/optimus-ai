from memory.manager import MemoryManager

def verify_context_integration():
    print("🕵️ Verifying Tool Patterns in AI Context...")

    # 1. Initialize
    manager = MemoryManager.initialize()

    # 2. Seed a unique test pattern 
    # (We use a unique string so we can be 100% sure we found THIS record)
    test_tool = "verify_context_tool"
    test_pattern = "ALWAYS verify the context string contains this specific test phrase."
    
    print(f"📝 Seeding temporary test pattern for '{test_tool}'...")
    memory_item = manager.store_tool_pattern(
        tool_name=test_tool,
        pattern=test_pattern,
        success=True,
        importance=1.0 # High importance to ensure it isn't filtered out
    )

    # 3. Generate the context string
    print("🔄 Building context string...")
    # We explicitly ask for tool patterns, though defaults might already include it
    context = manager.build_context_string(include_tool_pattern=True)

    # 4. Verify the output
    print("\n🔍 Analyzing Context Output:")
    
    header_found = "=== Tool Patterns ===" in context
    content_found = test_pattern in context

    if header_found:
        print("   ✅ Found 'Tool Patterns' section header.")
    else:
        print("   ❌ Missing 'Tool Patterns' section header.")

    if content_found:
        print(f"   ✅ Found specific pattern text.")
    else:
        print(f"   ❌ Could not find pattern text: '{test_pattern}'")
    
    # 5. Visual Confirmation
    if header_found:
        start = context.find("=== Tool Patterns ===")
        # Find the start of the NEXT section (if any) to slice just the relevant part
        # We look for "=== " occurring after our current header
        next_section = context.find("\n=== ", start + 5)
        
        if next_section == -1:
            snippet = context[start:]
        else:
            snippet = context[start:next_section]
            
        print("\n--- 📄 Captured Context Snippet ---")
        print(snippet.strip())
        print("-----------------------------------")

    # 6. Cleanup
    print("\n🧹 Cleaning up test data...")
    manager.store.delete(memory_item.id)
    manager.close()
    
    if header_found and content_found:
        print("\n🎉 SUCCESS: The AI is receiving tool patterns!")
    else:
        print("\n⛔ FAILURE: Context integration is incomplete.")

if __name__ == "__main__":
    verify_context_integration()