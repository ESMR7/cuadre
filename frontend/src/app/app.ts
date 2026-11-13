import { Component, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { ApiService } from './nucleo/api.service';
import { SesionService } from './nucleo/sesion.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <header class="encabezado">
      <div class="contenedor">
        <a class="marca" routerLink="/"><span class="marca-icono">C</span>Cuadre</a>
        @if (sesion.token()) {
          <nav class="nav">
            <a routerLink="/cuenta" routerLinkActive="activo">Mi cuenta</a>
            <a routerLink="/bolsas" routerLinkActive="activo">Mis bolsas</a>
          </nav>
          <button class="boton secundario pequeno" (click)="salir()">Salir</button>
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
