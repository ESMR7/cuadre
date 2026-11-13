import { Injectable, inject, signal } from '@angular/core';

import { ApiService } from './api.service';
import { ResumenBolsa } from './tipos';

/**
 * Aviso al iniciar sesión (SPEC 9.4): bolsas abiertas o canceladas donde mi
 * estado es pendiente o por_confirmar.
 */
@Injectable({ providedIn: 'root' })
export class AvisoService {
  private readonly api = inject(ApiService);
  readonly pendientes = signal<ResumenBolsa[]>([]);

  consultar(): void {
    this.api.bolsas(0, 100).subscribe({
      next: (lista) => this.pendientes.set(lista.bolsas.filter(requiereAccion)),
      error: () => this.pendientes.set([]),
    });
  }

  limpiar(): void {
    this.pendientes.set([]);
  }
}

export function requiereAccion(b: ResumenBolsa): boolean {
  return (
    (b.estado === 'abierta' || b.estado === 'cancelada') &&
    (b.mi_estado === 'pendiente' || b.mi_estado === 'por_confirmar')
  );
}
