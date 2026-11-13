import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { ApiService } from '../nucleo/api.service';
import { AvisoService } from '../nucleo/aviso.service';
import { mensajeDe } from '../nucleo/errores';
import { SesionService } from '../nucleo/sesion.service';

/** Registro e inicio de sesión. Ninguna de las dos se reintenta sola. */
@Component({
  selector: 'app-acceso',
  imports: [FormsModule],
  template: `
    <header class="portada">
      <span class="etiqueta">Billetera digital</span>
      <h1>Pagos en grupo, cuentas exactas.</h1>
      <p>Carga saldo, transfiere y arma bolsas con tus amigos sin que se pierda un peso.</p>
    </header>

    <div class="estrecho">
      @if (error()) {
        <div class="alerta">
          <span class="etiqueta">Error</span>
          <p>{{ error() }}</p>
        </div>
      }
      @if (exito()) {
        <p class="exito">{{ exito() }}</p>
      }
    </div>

    <div class="columnas">
      <section class="tarjeta formulario">
        <span class="etiqueta">Ya tengo cuenta</span>
        <h2>Iniciar sesión</h2>
        <form (ngSubmit)="entrar()">
          <label
            >Usuario <input name="u" [(ngModel)]="usuario" autocomplete="username" required
          /></label>
          <label
            >Contraseña
            <input
              name="c"
              type="password"
              [(ngModel)]="contrasena"
              autocomplete="current-password"
              required
            />
          </label>
          <button class="boton" [disabled]="ocupado()">Entrar</button>
        </form>
      </section>
      <section class="tarjeta formulario">
        <span class="etiqueta">Nuevo en Cuadre</span>
        <h2>Registrarme</h2>
        <form (ngSubmit)="registrar()">
          <label>Usuario <input name="ru" [(ngModel)]="nuevoUsuario" required /></label>
          <label
            >Cédula <input name="rc" [(ngModel)]="cedula" inputmode="numeric" required
          /></label>
          <label
            >Contraseña
            <input
              name="rp"
              type="password"
              [(ngModel)]="nuevaContrasena"
              autocomplete="new-password"
              required
            />
          </label>
          <button class="boton secundario" [disabled]="ocupado()">Crear cuenta</button>
        </form>
      </section>
    </div>
  `,
})
export class Acceso {
  private readonly api = inject(ApiService);
  private readonly sesion = inject(SesionService);
  private readonly aviso = inject(AvisoService);
  private readonly router = inject(Router);

  usuario = '';
  contrasena = '';
  nuevoUsuario = '';
  cedula = '';
  nuevaContrasena = '';
  readonly ocupado = signal(false);
  readonly error = signal<string | null>(null);
  readonly exito = signal<string | null>(null);

  entrar(): void {
    this.inicio();
    this.api.iniciarSesion(this.usuario.trim(), this.contrasena).subscribe({
      next: (s) => {
        this.sesion.iniciar(s.token);
        this.contrasena = '';
        this.aviso.consultar();
        void this.router.navigate(['/cuenta']);
      },
      error: (e) => this.fallo(e),
    });
  }

  registrar(): void {
    this.inicio();
    this.api
      .registrar(this.nuevoUsuario.trim(), this.cedula.trim(), this.nuevaContrasena)
      .subscribe({
        next: () => {
          this.ocupado.set(false);
          this.usuario = this.nuevoUsuario.trim();
          this.nuevaContrasena = '';
          this.cedula = '';
          this.exito.set('Cuenta creada. Ya puedes iniciar sesión.');
        },
        error: (e) => this.fallo(e),
      });
  }

  private inicio(): void {
    this.ocupado.set(true);
    this.error.set(null);
    this.exito.set(null);
  }

  private fallo(e: unknown): void {
    this.ocupado.set(false);
    this.error.set(mensajeDe(e));
  }
}
