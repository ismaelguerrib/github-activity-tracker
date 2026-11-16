#!/usr/bin/env python3
"""Local web interface for the GitHub CLI activity tracker."""
import argparse
import csv
import io
import json
import mimetypes
import re
import secrets
import shlex
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from xml.sax.saxutils import escape

from extract_activity_gh import GitHubCLIActivityTracker

ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / 'frontend' / 'dist' / 'frontend' / 'browser'
JOBS = {}
LOCK = threading.Lock()


def validate(data):
    if not isinstance(data, dict):
        raise ValueError('Paramètres invalides.')
    result = {}
    for field in ('org', 'user'):
        value = data.get(field, '')
        if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,99}', value):
            raise ValueError('Organisation et utilisateur : utilisez un identifiant GitHub valide.')
        result[field] = value
    for field, low, high in [('year', 2008, 9998), ('month', 1, 12), ('repo_limit', 1, 1000)]:
        value = data.get(field)
        if isinstance(value, bool) or not re.fullmatch(r'\d+', str(value)) or not low <= int(value) <= high:
            raise ValueError(f'Valeur invalide pour {field} ({low} à {high}).')
        result[field] = int(value)
    if data.get('method') not in ('both', 'repos', 'search'):
        raise ValueError('Méthode invalide.')
    result['method'] = data['method']
    repos = data.get('include_repos', '')
    if not isinstance(repos, str) or len(repos) > 4000:
        raise ValueError('Liste de dépôts invalide.')
    names = [r.strip() for r in repos.split(',') if r.strip()]
    if any(not re.fullmatch(r'[A-Za-z0-9_.-]+', r) or r in ('.', '..') or r.endswith('.wiki') for r in names):
        raise ValueError('Utilisez les noms des dépôts parents, sans organisation ni suffixe .wiki.')
    result['include_repos'] = ','.join(names)
    result['verbose'] = data.get('verbose') is True
    return result


def command(params):
    args = ['python3', 'extract_activity_gh.py', '--org', params['org'], '--user', params['user'],
            '--year', str(params['year']), '--month', str(params['month']), '--method', params['method'],
            '--repo-limit', str(params['repo_limit'])]
    if params['include_repos']:
        args += ['--include-repos', params['include_repos']]
    if params['verbose']:
        args += ['--verbose']
    return shlex.join(args + ['--output', 'activity_report.json'])


def run_job(job_id, params):
    try:
        tracker = GitHubCLIActivityTracker(params['org'], params['user'], params['year'], params['month'], params['verbose'])
        if not tracker.check_gh_cli():
            raise RuntimeError('GitHub CLI indisponible ou non connecté. Exécutez gh auth login dans votre terminal.')
        days = set()
        if params['method'] in ('repos', 'both'):
            days.update(tracker.get_user_activity(repo_limit=params['repo_limit'], include_repos=params['include_repos'].split(',') if params['include_repos'] else []))
        if params['method'] in ('search', 'both'):
            days.update(tracker.get_user_search_activity())
        report = dict(user=params['user'], organization=params['org'], year=params['year'], month=params['month'],
                      active_days=sorted(days), total_active_days=len(days), daily_activity_details=dict(tracker.daily_activity),
                      method_used=params['method'], complete=not tracker.failures, failures=tracker.failures,
                      generated_at=datetime.now().astimezone().isoformat(), api_requests=tracker.api_call_count)
        with LOCK:
            JOBS[job_id].update(status='done', report=report)
    except Exception as exc:
        with LOCK:
            JOBS[job_id].update(status='error', error=str(exc))


def csv_report(report):
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['organization', 'user', 'period', 'complete', 'date', 'activity', 'failures'])
    prefix = [report['organization'], report['user'], f"{report['year']}-{report['month']:02d}", report['complete']]
    def safe(value):
        value = str(value)
        return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value
    for day in report['active_days'] or ['']:
        for detail in report['daily_activity_details'].get(day, []) or ['']:
            writer.writerow([safe(v) for v in prefix + [day, detail, ' | '.join(report['failures'])]])
    return output.getvalue().encode('utf-8-sig')


def pdf_report(report):
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.enums import TA_LEFT
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    stream = io.BytesIO()
    styles = getSampleStyleSheet()
    styles['Title'].alignment = TA_LEFT
    styles['Title'].textColor = colors.HexColor('#174b39')
    styles['BodyText'].leading = 15
    story = [Paragraph("GitHub Activity Report", styles['Title']),
             Paragraph(escape(f"{report['organization']} / {report['user']}"), styles['Heading2']),
             Paragraph(f"{report['year']}-{report['month']:02d} · {report['total_active_days']} jours actifs", styles['Heading2']),
             Paragraph(escape('Généré le ' + report['generated_at']), styles['BodyText']), Spacer(1, 16)]
    if not report['complete']:
        story += [Paragraph('Rapport incomplet : certaines activités peuvent manquer.', styles['Heading2'])]
        story += [Paragraph(escape(f), styles['BodyText']) for f in report['failures']]
    if not report['active_days']:
        story += [Paragraph('Aucune activité trouvée pour cette période.', styles['BodyText'])]
    for day in report['active_days']:
        story.append(Paragraph(escape(day), styles['Heading2']))
        for detail in report['daily_activity_details'].get(day, []):
            story.append(Paragraph(escape(detail), styles['BodyText']))
        story.append(Spacer(1, 8))
    def footer(canvas, doc):
        canvas.setFont('Helvetica', 9)
        canvas.drawString(42, 24, 'GitHub Activity Tracker')
        canvas.drawRightString(550, 24, str(doc.page))
    SimpleDocTemplate(stream, title='GitHub Activity Report', rightMargin=42, leftMargin=42,
                      topMargin=42, bottomMargin=42).build(story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, body, content_type='application/json; charset=utf-8', filename=None):
        if isinstance(body, dict):
            body = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if filename:
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    def serve_static(self, path):
        # Serve the built Angular app; unknown non-API paths fall back to index.html (SPA).
        target = (WEB_ROOT / (path.lstrip('/') or 'index.html')).resolve()
        if (target == WEB_ROOT or WEB_ROOT in target.parents) and target.is_file():
            ctype = mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
            if ctype.startswith('text/') or ctype in ('application/javascript', 'application/json'):
                ctype += '; charset=utf-8'
            return self.respond(200, target.read_bytes(), ctype)
        index = WEB_ROOT / 'index.html'
        if index.is_file():
            return self.respond(200, index.read_bytes(), 'text/html; charset=utf-8')
        return self.respond(503, {'error': 'Frontend non compilé. Exécutez : npm --prefix frontend ci && npm --prefix frontend run build.'})

    def do_GET(self):
        path = urlparse(self.path).path
        match = re.fullmatch(r'/api/reports/([a-f0-9]{32})(?:\.(csv|pdf))?', path)
        if match:
            with LOCK:
                job = dict(JOBS.get(match[1], {}))
            if not job:
                return self.respond(404, {'error': 'Rapport introuvable ou expiré.'})
            fmt = match[2]
            if not fmt:
                return self.respond(200, {k: v for k, v in job.items() if k != 'created'})
            if job['status'] != 'done':
                return self.respond(409, {'error': 'Le rapport n’est pas encore disponible.'})
            try:
                report = job['report']
                body = csv_report(report) if fmt == 'csv' else pdf_report(report)
                filename = f"activity-{report['organization']}-{report['user']}-{report['year']}-{report['month']:02d}.{fmt}"
                return self.respond(200, body, 'text/csv; charset=utf-8' if fmt == 'csv' else 'application/pdf', filename)
            except ImportError:
                return self.respond(503, {'error': 'Export PDF indisponible. Installez requirements.txt.'})
        if path.startswith('/api/'):
            return self.respond(404, {'error': 'Route introuvable.'})
        self.serve_static(path)

    def do_POST(self):
        # Only same-origin JSON requests may trigger the authenticated local CLI.
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host', ''):
            return self.respond(403, {'error': 'Origine refusée.'})
        if self.path != '/api/reports':
            return self.respond(404, {'error': 'Route introuvable.'})
        try:
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('Un corps JSON est requis.')
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 16384:
                raise ValueError('Requête trop volumineuse ou vide.')
            params = validate(json.loads(self.rfile.read(size)))
        except (ValueError, TypeError):
            return self.respond(400, {'error': 'Paramètres invalides. Vérifiez les identifiants, la période et les options.'})
        with LOCK:
            for key in list(JOBS):
                if JOBS[key]['status'] != 'running' and time.time() - JOBS[key]['created'] > 86400:
                    del JOBS[key]
            if any(job['status'] == 'running' for job in JOBS.values()):
                return self.respond(429, {'error': 'Une analyse est déjà en cours. Patientez avant de réessayer.'})
            job_id = secrets.token_hex(16)
            JOBS[job_id] = {'status': 'running', 'created': time.time(), 'command': command(params)}
        threading.Thread(target=run_job, args=(job_id, params), daemon=True).start()
        self.respond(202, {'id': job_id})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    print(f'GitHub Activity Tracker : http://127.0.0.1:{args.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
