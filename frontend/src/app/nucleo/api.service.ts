import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { Bolsa, Historial, ListaBolsas, NuevaBolsa, Saldo, Sesion, Transaccion } from './tipos';

// Un método por endpoint de SPEC 9.2. Ninguno reintenta solo: los reintentos
// los decide el usuario, y solo en las operaciones con clave.
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly url = environment.apiUrl;

  registrar(nombre_usuario: string, cedula: string, contrasena: string): Observable<unknown> {
    return this.http.post(`${this.url}/usuarios`, { nombre_usuario, cedula, contrasena });
  }

  iniciarSesion(nombre_usuario: string, contrasena: string): Observable<Sesion> {
    return this.http.post<Sesion>(`${this.url}/sesiones`, { nombre_usuario, contrasena });
  }

  cerrarSesion(): Observable<unknown> {
    return this.http.delete(`${this.url}/sesiones`);
  }

  cuenta(): Observable<Saldo> {
    return this.http.get<Saldo>(`${this.url}/cuenta`);
  }

  movimientos(desde: number, cantidad: number): Observable<Historial> {
    const params = new HttpParams().set('desde', desde).set('cantidad', cantidad);
    return this.http.get<Historial>(`${this.url}/cuenta/movimientos`, { params });
  }

  cargar(monto: number, clave: string): Observable<Transaccion> {
    return this.http.post<Transaccion>(
      `${this.url}/cargas`,
      { monto },
      { headers: conClave(clave) },
    );
  }

  transferir(destino: string, monto: number, clave: string): Observable<Transaccion> {
    return this.http.post<Transaccion>(
      `${this.url}/transferencias`,
      { destino, monto },
      { headers: conClave(clave) },
    );
  }

  bolsas(desde: number, cantidad: number): Observable<ListaBolsas> {
    const params = new HttpParams().set('desde', desde).set('cantidad', cantidad);
    return this.http.get<ListaBolsas>(`${this.url}/bolsas`, { params });
  }

  bolsa(id: string): Observable<Bolsa> {
    return this.http.get<Bolsa>(`${this.url}/bolsas/${encodeURIComponent(id)}`);
  }

  crearBolsa(datos: NuevaBolsa): Observable<Bolsa> {
    return this.http.post<Bolsa>(`${this.url}/bolsas`, datos);
  }

  aportar(id: string, clave: string): Observable<Transaccion> {
    return this.http.post<Transaccion>(
      `${this.url}/bolsas/${encodeURIComponent(id)}/aportes`,
      null,
      {
        headers: conClave(clave),
      },
    );
  }

  retirarse(id: string, clave: string): Observable<unknown> {
    return this.http.post(`${this.url}/bolsas/${encodeURIComponent(id)}/retiro`, null, {
      headers: conClave(clave),
    });
  }

  confirmar(id: string): Observable<unknown> {
    return this.http.post(`${this.url}/bolsas/${encodeURIComponent(id)}/confirmacion`, null);
  }

  cancelar(id: string): Observable<unknown> {
    return this.http.post(`${this.url}/bolsas/${encodeURIComponent(id)}/cancelacion`, null);
  }
}

function conClave(clave: string): HttpHeaders {
  return new HttpHeaders({ 'Idempotency-Key': clave });
}
