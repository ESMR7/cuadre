import { Injectable } from '@angular/core';

/**
 * Claves de idempotencia por intención (SPEC 9.5).
 *
 * Una intención es, por ejemplo, 'transferir' o 'aportar:<id de bolsa>'. La
 * clave se crea con crypto.randomUUID() la primera vez que el usuario pulsa el
 * botón y se reutiliza en cada reintento de esa misma intención:
 * - se conserva ante un error de red o cualquier 5xx (incluido 503
 *   reintentos_agotados), porque no se sabe si la operación confirmó;
 * - se borra ante éxito, ante un 4xx definitivo o cuando el usuario cambia el
 *   formulario (eso ya es otra intención).
 */
@Injectable({ providedIn: 'root' })
export class IdempotenciaService {
  private readonly claves = new Map<string, string>();

  claveDe(intencion: string): string {
    let clave = this.claves.get(intencion);
    if (clave === undefined) {
      clave = crypto.randomUUID();
      this.claves.set(intencion, clave);
    }
    return clave;
  }

  /** La intención terminó con éxito. */
  exito(intencion: string): void {
    this.claves.delete(intencion);
  }

  /** La intención falló. `status` 0 es un error de red. */
  fallo(intencion: string, status: number): void {
    const reintentable = status === 0 || status >= 500;
    if (!reintentable) {
      this.claves.delete(intencion);
    }
  }

  /** El usuario cambió el formulario: la próxima vez es una intención nueva. */
  cambioFormulario(intencion: string): void {
    this.claves.delete(intencion);
  }

  /** Hay una clave pendiente: la interfaz ofrece "Reintentar". */
  pendiente(intencion: string): boolean {
    return this.claves.has(intencion);
  }
}
