import { Component, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { toSignal } from '@angular/core/rxjs-interop';
import { firstValueFrom } from 'rxjs';
import { Report, ReportParams, ReportService } from './report.service';

const ID = /^[A-Za-z0-9][A-Za-z0-9-]{0,99}$/;
const METHOD_NOTES: Record<string, string> = {
  both: 'Combine les deux méthodes et déduplique les résultats.',
  search: 'Plus rapide. Les éditions wiki et commentaires sur commits ne sont pas couverts.',
  repos: 'Explore les dépôts récents, découverts et ajoutés manuellement.',
};

function previousMonth(): string {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() - 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function shellQuote(value: string): string {
  return /^[A-Za-z0-9_.,/-]+$/.test(value) ? value : "'" + value.replaceAll("'", "'\\''") + "'";
}

@Component({
  selector: 'app-root',
  imports: [ReactiveFormsModule],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  private fb = inject(FormBuilder);
  private api = inject(ReportService);

  readonly form = this.fb.nonNullable.group({
    org: ['', [Validators.required, Validators.pattern(ID)]],
    user: ['', [Validators.required, Validators.pattern(ID)]],
    period: [previousMonth(), Validators.required],
    method: ['both' as 'both' | 'repos' | 'search', Validators.required],
    repo_limit: [20, [Validators.required, Validators.min(1), Validators.max(1000)]],
    include_repos: [''],
    verbose: [false],
  });

  private value = toSignal(this.form.valueChanges, { initialValue: this.form.getRawValue() });

  readonly status = signal<'idle' | 'running' | 'done' | 'error'>('idle');
  readonly report = signal<Report | null>(null);
  readonly errorMessage = signal('');
  readonly copied = signal(false);
  private reportId: string | null = null;

  /** Decorative heatmap cells (same pattern as the original landing visual). */
  readonly heatmap = Array.from({ length: 48 }, (_, i) => ((i * 7 + Math.floor(i / 4)) % 5 < 2 ? 0 : ((i + Math.floor(i / 7)) % 3) + 1));

  readonly methodNote = computed(() => METHOD_NOTES[this.value().method ?? 'both']);

  readonly contributions = computed(() => {
    const r = this.report();
    return r ? Object.values(r.daily_activity_details).reduce((sum, entries) => sum + entries.length, 0) : 0;
  });

  readonly badge = computed(() => {
    switch (this.status()) {
      case 'running': return 'EN COURS';
      case 'error': return 'ERREUR';
      case 'done': return this.report()?.complete ? 'TERMINÉ' : 'INCOMPLET';
      default: return 'EN ATTENTE';
    }
  });

  readonly command = computed(() => {
    const p = this.params();
    const args = ['python3', 'extract_activity_gh.py', '--org', p.org || 'organisation', '--user', p.user || 'utilisateur',
      '--year', String(p.year), '--month', String(p.month), '--method', p.method, '--repo-limit', String(p.repo_limit)];
    if (p.include_repos) args.push('--include-repos', p.include_repos);
    if (p.verbose) args.push('--verbose');
    args.push('--output', 'activity_report.json');
    return args.map(shellQuote).join(' ');
  });

  private params(): ReportParams {
    const v = this.value();
    const [year, month] = (v.period ?? previousMonth()).split('-').map(Number);
    return {
      org: (v.org ?? '').trim(),
      user: (v.user ?? '').trim(),
      year, month,
      method: v.method ?? 'both',
      repo_limit: Number(v.repo_limit ?? 20),
      include_repos: (v.include_repos ?? '').trim(),
      verbose: !!v.verbose,
    };
  }

  dayLabel(day: string): string {
    return new Date(day + 'T12:00:00').toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
  }

  async copyCommand(): Promise<void> {
    try {
      await navigator.clipboard.writeText(this.command());
      this.copied.set(true);
      setTimeout(() => this.copied.set(false), 2000);
    } catch { /* clipboard unavailable: leave the command visible to copy manually */ }
  }

  async submit(): Promise<void> {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.status.set('running');
    this.report.set(null);
    this.reportId = null;
    try {
      const { id } = await firstValueFrom(this.api.start(this.params()));
      this.reportId = id;
      let job = await firstValueFrom(this.api.poll(id));
      while (job.status === 'running') {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        job = await firstValueFrom(this.api.poll(id));
      }
      if (job.status === 'error') throw new Error(job.error);
      this.report.set(job.report!);
      this.status.set('done');
    } catch (error: unknown) {
      this.errorMessage.set(this.messageOf(error));
      this.status.set('error');
    }
  }

  async download(format: 'csv' | 'pdf'): Promise<void> {
    if (!this.reportId) return;
    try {
      const response = await firstValueFrom(this.api.download(this.reportId, format));
      const blob = response.body!;
      const disposition = response.headers.get('Content-Disposition') ?? '';
      const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? `activity-report.${format}`;
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = name;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error: unknown) {
      this.errorMessage.set(this.messageOf(error));
    }
  }

  private messageOf(error: unknown): string {
    const e = error as { error?: { error?: string }; message?: string };
    return e?.error?.error || e?.message || 'Une erreur est survenue.';
  }
}
