"""Example code with intentional issues for testing code review agent."""

import os
import pickle
import time

# Hardcoded secret (should be detected)
API_KEY = "sk-1234567890abcdef"
DATABASE_PASSWORD = "admin123"


class DataProcessor:
    """A data processor with several code quality issues."""

    def __init__(self, config_path):
        self.config_path = config_path
        self.data = None
        self.buffer = []  # Mutable default issue

    def load_config(self):
        """Load config without error handling."""
        # Path traversal vulnerability
        with open(self.config_path, 'r') as f:
            config = f.read()
        return config

    def process_data(self, data):
        """Process data with unsafe deserialization."""
        # Unsafe deserialization
        self.data = pickle.loads(data)

        # Missing key validation
        result = self.data['points']
        return result

    def save_result(self, result, path):
        """Save result with SQL injection risk."""
        # SQL injection
        query = f"INSERT INTO results VALUES ('{result}')"

        # Resource leak - file not closed
        f = open(path, 'w')
        f.write(str(result))
        # Missing f.close()

    def wait_for_data(self):
        """Wait with blocking sleep."""
        # Blocking sleep in critical path
        time.sleep(5)
        return self.buffer

    def process_batch(self, items):
        """Process batch with O(n²) complexity."""
        # O(n²) nested loop
        results = []
        for item in items:
            for other in items:
                if item != other:
                    results.append((item, other))
        return results


def unsafe_function(user_input):
    """Function with eval vulnerability."""
    # Code injection risk
    return eval(user_input)


# TODO: Fix this later
def incomplete_function():
    pass
