#!/usr/bin/env python3
"""Publica el CSV del usuario y sus pesos en un único commit en GitHub."""
import argparse
import base64
import getpass
import json
import os
from pathlib import Path
import subprocess
import urllib.error
import urllib.request

from weights import apply_weights, read_weights, weights_payload


def api(token, repository, method, path, data=None):
    request = urllib.request.Request(
        f'https://api.github.com/repos/{repository}/{path}',
        data=json.dumps(data).encode() if data is not None else None,
        method=method, headers={'Authorization': f'Bearer {token}',
                               'Accept': 'application/vnd.github+json',
                               'Content-Type': 'application/json',
                               'User-Agent': 'SPY-Weights-Updater'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'GitHub respondió HTTP {exc.code}. Revisá permisos y si main cambió; no se fuerza el push.') from None


def publish(csv_text, items, token, repository):
    def call(method, path, data=None):
        return api(token, repository, method, path, data)
    head = call('GET', 'git/ref/heads/main')['object']['sha']
    commit = call('GET', f'git/commits/{head}')
    source = call('GET', f'contents/SPY_data.json?ref={head}')
    feed = json.loads(base64.b64decode(source['content']))
    base_source = call('GET', f'contents/SPY_componentes_base.json?ref={head}')
    old_items = json.loads(base64.b64decode(base_source['content']))['componentes']
    if old_items == items:
        return None
    files = {'spy500.csv': csv_text,
             'SPY_componentes_base.json': json.dumps(weights_payload(items), ensure_ascii=False, indent=2) + '\n',
             'SPY_data.json': json.dumps(apply_weights(feed, items), ensure_ascii=False, indent=2) + '\n'}
    entries = []
    for name, content in files.items():
        blob = call('POST', 'git/blobs', {'content': content, 'encoding': 'utf-8'})
        entries.append({'path': name, 'mode': '100644', 'type': 'blob', 'sha': blob['sha']})
    tree = call('POST', 'git/trees', {'base_tree': commit['tree']['sha'], 'tree': entries})
    new_commit = call('POST', 'git/commits', {
        'message': 'Actualizar pesos del SPY desde CSV del usuario',
        'tree': tree['sha'], 'parents': [head]})
    # GitHub rejects this non-forced update if another writer advanced main.
    call('PATCH', 'git/refs/heads/main', {'sha': new_commit['sha'], 'force': False})
    return f'https://github.com/{repository}/commit/{new_commit["sha"]}'


def choose_csv():
    for command in (['kdialog', '--getopenfilename', str(Path.home()), '*.csv'],
                    ['zenity', '--file-selection', '--title=Seleccionar CSV de pesos']):
        try:
            result = subprocess.run(command, capture_output=True, text=True)
        except FileNotFoundError:
            continue
        if result.returncode != 0:
            raise RuntimeError('Selección cancelada; no se publicó ningún cambio.')
        return Path(result.stdout.strip())
    return Path(input('Ruta del archivo CSV: ').strip().strip('"'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path)
    parser.add_argument('--repo', default='isaiasgonzalez/spy-tracker')
    parser.add_argument('--dry-run', action='store_true', help='Validar CSV sin conectarse a GitHub')
    args = parser.parse_args()
    text = (args.csv or choose_csv()).read_text(encoding='utf-8-sig')
    items = read_weights(text)
    print(f'CSV válido: {len(items)} acciones; peso total {sum(i["peso_pct"] for i in items):.4f}%.')
    if args.dry_run:
        return
    print(f'Publicando directamente en {args.repo}, rama main.')
    token = os.environ.get('SPY_GITHUB_TOKEN') or getpass.getpass('Token de GitHub (entrada oculta, no se guarda): ')
    if not token:
        raise RuntimeError('Falta el token de GitHub.')
    url = publish(text, items, token, args.repo)
    print(f'Publicado: {url}' if url else 'Los pesos ya coinciden; no se creó un commit.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Error: {exc}')
        raise SystemExit(1)
