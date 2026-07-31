.PHONY: all install lint fix test build clean

all: README.md

# Generate into a temporary file first, so a failing generator does not
# truncate the committed README.md.
README.md: README.jinja2.md generate_readme.py src/masscan_as_a_service/__main__.py
	uv run ./generate_readme.py > $@.tmp
	mv $@.tmp $@

install:
	uv sync

lint:
	uv run ruff check .

fix:
	uv run ruff check --fix .

test:
	uv run pytest

build:
	uv build

clean:
	rm -rf build dist src/*.egg-info .pytest_cache .ruff_cache README.md.tmp
