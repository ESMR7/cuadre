import { Injectable, signal } from '@angular/core';

const LLAVE = 'cuadre.token';

/** Guarda el token de sesión que emite la API (SPEC 9.1). */
@Injectable({ providedIn: 'root' })
export class SesionService {
  readonly token = signal<string | null>(leer());
  readonly usuario = signal<string | null>(null);

  iniciar(token: string): void {
    escribir(token);
    this.token.set(token);
  }

  cerrar(): void {
    escribir(null);
    this.token.set(null);
    this.usuario.set(null);
  }

  autenticado(): boolean {
    return this.token() !== null;
  }
}

function leer(): string | null {
  try {
    return sessionStorage.getItem(LLAVE);
  } catch {
    return null;
  }
}

function escribir(token: string | null): void {
  try {
    if (token === null) {
      sessionStorage.removeItem(LLAVE);
    } else {
      sessionStorage.setItem(LLAVE, token);
    }
  } catch {
    // Sin almacenamiento: la sesión vive solo en memoria.
  }
}
