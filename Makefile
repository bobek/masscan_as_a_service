all: requirements.txt README.md

requirements.txt: Pipfile
		python3 -c "from pipenv.vendor import toml; out = open('requirements.txt', 'w'); out.write('# Auto-generated!\n\n' + '\n'.join(package + ('' if version == '*' else version) for package, version in toml.load('Pipfile')['packages'].items()))"

README.md: README.jinja2.md
	./generate_readme.py > README.md
