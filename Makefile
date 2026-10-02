.PHONY: test demo clean

PYTHON ?= python3

test:
	$(PYTHON) -m unittest discover -s tests -t . -v

demo:
	@printf '%s\n' 'Привет, мир! Это URL-slug.' | $(PYTHON) slugify.py

clean:
	rm -rf __pycache__ tests/__pycache__
