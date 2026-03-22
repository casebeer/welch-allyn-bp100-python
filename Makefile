
default: /dev/null
	@echo 'Install with pip install -e .[test]' >&2

clean: /dev/null
	find bp100 -type d -name __pycache__ -exec rm -rf -- {} +
	find . -type d -name '*.egg-info' -exec rm -rf -- {} +
