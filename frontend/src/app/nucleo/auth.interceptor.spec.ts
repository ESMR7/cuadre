import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { environment } from '../../environments/environment';
import { authInterceptor } from './auth.interceptor';
import { SesionService } from './sesion.service';

describe('authInterceptor', () => {
  let http: HttpClient;
  let control: HttpTestingController;
  const api = environment.apiUrl;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpClient);
    control = TestBed.inject(HttpTestingController);
    TestBed.inject(SesionService).iniciar('token-de-prueba');
  });

  afterEach(() => {
    control.verify();
    TestBed.inject(SesionService).cerrar();
  });

  function autorizacion(metodo: string, url: string): string | null {
    const peticion = control.expectOne((r) => r.method === metodo && r.url === url);
    const valor = peticion.request.headers.get('Authorization');
    peticion.flush({});
    return valor;
  }

  it('no agrega el token a POST /usuarios', () => {
    http.post(`${api}/usuarios`, {}).subscribe();
    expect(autorizacion('POST', `${api}/usuarios`)).toBeNull();
  });

  it('no agrega el token a POST /sesiones', () => {
    http.post(`${api}/sesiones`, {}).subscribe();
    expect(autorizacion('POST', `${api}/sesiones`)).toBeNull();
  });

  it('agrega el token a POST /sesiones/renovar', () => {
    http.post(`${api}/sesiones/renovar`, null).subscribe();
    expect(autorizacion('POST', `${api}/sesiones/renovar`)).toBe('Bearer token-de-prueba');
  });

  it('agrega el token a DELETE /sesiones', () => {
    http.delete(`${api}/sesiones`).subscribe();
    expect(autorizacion('DELETE', `${api}/sesiones`)).toBe('Bearer token-de-prueba');
  });

  it('agrega el token a GET /cuenta', () => {
    http.get(`${api}/cuenta`).subscribe();
    expect(autorizacion('GET', `${api}/cuenta`)).toBe('Bearer token-de-prueba');
  });
});
