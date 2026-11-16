import { HttpClient, HttpResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

export interface ReportParams {
  org: string;
  user: string;
  year: number;
  month: number;
  method: 'both' | 'repos' | 'search';
  repo_limit: number;
  include_repos: string;
  verbose: boolean;
}

export interface Report {
  organization: string;
  user: string;
  year: number;
  month: number;
  complete: boolean;
  failures: string[];
  active_days: string[];
  total_active_days: number;
  daily_activity_details: Record<string, string[]>;
  method_used: string;
  generated_at: string;
}

export interface JobStatus {
  status: 'running' | 'done' | 'error';
  report?: Report;
  error?: string;
}

/** Thin wrapper over the local Python API; no logic beyond the HTTP calls. */
@Injectable({ providedIn: 'root' })
export class ReportService {
  private http = inject(HttpClient);

  start(params: ReportParams): Observable<{ id: string }> {
    return this.http.post<{ id: string }>('/api/reports', params);
  }

  poll(id: string): Observable<JobStatus> {
    return this.http.get<JobStatus>(`/api/reports/${id}`);
  }

  download(id: string, format: 'csv' | 'pdf'): Observable<HttpResponse<Blob>> {
    return this.http.get(`/api/reports/${id}.${format}`, { observe: 'response', responseType: 'blob' });
  }
}
