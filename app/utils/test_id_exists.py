def test_id_exists(table, test_id):
    """Check if a test ID already exists in the provided DynamoDB table."""
    response = table.get_item(Key={'id': test_id})
    return 'Item' in response


def test_id_exists_in_memory(test_instances, test_id):
    """Check if a test ID exists in the in-memory list."""
    return any(instance["test_id"] == test_id for instance in test_instances)