import { Component, inject } from '@angular/core';
import { Router, RouterLink, RouterOutlet } from '@angular/router';

import { ApiService } from './nucleo/api.service';
import { SesionService } from './nucleo/sesion.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink],
  template: `
    <header class="encabezado">
      <div class="contenedor">
        <a class="marca" routerLink="/">Cuadre</a>
        @if (sesion.token()) {
          <a routerLink="/cuenta">Mi cuenta</a>
          <a routerLink="/bolsas">Mis bolsas</a>
          <button class="boton secundario" (click)="salir()">Salir</button>
        }
      </div>
    </header>
    <main class="contenedor"><router-outlet /></main>
  `,
})
export class App {
  protected readonly sesion = inject(SesionService);
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);

  salir(): void {
    // Sin reintento: si falla, igual se olvida el token localmente.
    this.api.cerrarSesion().subscribe({ error: () => undefined });
    this.sesion.cerrar();
    void this.router.navigate(['/acceso']);
  }
}
