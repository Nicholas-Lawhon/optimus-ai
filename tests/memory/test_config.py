from memory.config import MemoryConfig, MemoryType, MemoryScope


def test_config_loads():
    config = MemoryConfig()
    print(f"Storage path: {config.storage_path}")
    print(f"Conversation TTL: {config.retention.get_ttl(MemoryType.CONVERSATION)}")

    issues = config.validate()
    print(f"Validation issues: {issues}")

    assert len(issues) == 0
