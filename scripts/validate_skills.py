"""Validate the authored package and its version-bound repository evidence."""
import hashlib
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACKAGE = REPO / 'skills/statistics-probability'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(package=PACKAGE, repo=REPO):
    manifest = load(package / 'references/manifest.json')
    sources = load(package / 'references/sources.json')
    expected = {package / manifest['root']}
    names = {s['name'] for s in manifest['skills']}
    require(len(names) == len(manifest['skills']), 'Duplicate skill identity')
    graph = {s['name']: s['prerequisites'] for s in manifest['skills']}
    def visit(name, stack):
        require(name in graph, 'Unknown prerequisite: ' + name)
        require(name not in stack, 'Circular prerequisite: ' + name)
        for prerequisite in graph[name]:
            visit(prerequisite, stack | {name})
    for name in graph:
        visit(name, set())
    for skill in manifest['skills']:
        require(skill['path'] == f"subskills/{skill['name']}/SKILL.md", 'Unsupported nesting')
        expected.add(package / skill['path'])
        for field in ('input_contract', 'output_contract', 'known_limitations', 'coverage', 'evidence'):
            require(bool(skill[field]), 'Missing contract: ' + field)
    require(set(package.rglob('SKILL.md')) == expected, 'Missing or unregistered skill/nesting')
    for path in expected:
        text = path.read_text(encoding='utf-8')
        match = re.match(r'\A---\nname: ([a-z0-9-]+)\ndescription: ("[^\n]+")\n---\n', text)
        require(match is not None, 'Expected controlled YAML metadata: ' + str(path))
        name, quoted = match.groups()
        require(name == path.parent.name and len(name) <= 64 and '--' not in name
                and not name.startswith('-') and not name.endswith('-'), 'Invalid skill name')
        description = json.loads(quoted)
        require(0 < len(description) <= 1024, 'Invalid description')
        require('\u2014' not in text, 'Em dash in skill instructions')
    for path in package.rglob('*.md'):
        for target in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
            if '://' not in target and not target.startswith('#'):
                destination = (path.parent / target.split('#')[0]).resolve()
                require(destination.is_relative_to(package.resolve()) and destination.exists(),
                        'Missing or escaping local reference: ' + str(path) + ': ' + target)
    run = repo / sources['ingestion']['path']
    analysis_path = run / 'analysis.json'
    require(hashlib.sha256(analysis_path.read_bytes()).hexdigest() == sources['ingestion']['analysis_sha256'],
            'Ingestion evidence changed; review affected skills')
    analysis = load(analysis_path)
    for source in sources['sources'].values():
        for path_key, hash_key in [('file', 'sha256'), ('native_content', 'content_sha256')]:
            require(hashlib.sha256((repo / source[path_key]).read_bytes()).hexdigest() == source[hash_key],
                    'Source revision drift: ' + source[path_key])
    evidence_count = 0
    for skill in manifest['skills']:
        source = sources['sources'][skill['coverage']['source']]
        excerpts = load(package / skill['evidence'])
        require([e['slide'] for e in excerpts] == skill['coverage']['slides'], 'Incomplete coverage')
        for excerpt in excerpts:
            require(1 <= excerpt['slide'] <= source['slide_count'], 'Slide outside source')
            require(excerpt['source_sha256'] == source['sha256'], 'Evidence source mismatch')
            task = f"{source['sha256'][:16]}-s{excerpt['slide']:03}"
            report = next(r for r in analysis['reports'] if r['task_id'] == task)
            require(excerpt['units'] == report['units'],
                    'Evidence differs from validated ingestion: ' + task)
            require(excerpt['issues'] == report['issues'] and excerpt['limitations'] == report['limitations'],
                    'Source caveat omitted: ' + task)
            evidence_count += sum(len(unit['evidence']) for unit in excerpt['units'])
    return dict(skills=len(expected), source_versions=len(sources['sources']),
                evidence_entries=evidence_count, status='passed')


if __name__ == '__main__':
    print(json.dumps(validate(), indent=2))
