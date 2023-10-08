import unittest

if __name__ == "__main__":
    # Discover and run all tests in the 'src' directory
    loader = unittest.TestLoader()
    suite = loader.discover('src', pattern='test*.py')
    runner = unittest.TextTestRunner()
    runner.run(suite)
