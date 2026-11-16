import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { App } from './app';

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('should render the hero title', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('h1')?.textContent).toContain('Votre travail');
  });

  it('builds the equivalent CLI command from the form', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    app.form.patchValue({ org: 'acme', user: 'alice', period: '2026-10', method: 'both' });
    fixture.detectChanges();
    expect(app.command()).toContain('--org acme --user alice --year 2026 --month 10');
  });
});
