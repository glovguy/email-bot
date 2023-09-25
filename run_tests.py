import unittest

if __name__ == "__main__":
    # Discover and run all tests in the 'app' directory
    loader = unittest.TestLoader()
    suite = loader.discover('app', pattern='test*.py')
    runner = unittest.TextTestRunner()
    runner.run(suite)
