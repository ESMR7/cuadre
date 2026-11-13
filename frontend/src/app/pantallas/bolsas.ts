import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { ApiService } from '../nucleo/api.service';
import { mensajeDe } from '../nucleo/errores';
import { FechaBogotaPipe, PesosPipe, fechaBogotaConZona, leerMonto } from '../nucleo/formato';
import { ResumenBolsa } from '../nucleo/tipos';

const POR_PAGINA = 20;

/** Mis bolsas, paginadas. */
@Component({
  selector: 'app-bolsas',
  imports: [RouterLink, PesosPipe, FechaBogotaPipe],
  template: `
    <div class="fila">
      <h1>Mis bolsas</h1>
      <a class="boton" routerLink="/bolsas/nueva">Crear bolsa</a>
    </div>
    @if (error()) {
      <div class="alerta">
        <span class="etiqueta">Error</span>
        <p>{{ error() }}</p>
      </div>
    }
    @for (b of bolsas(); track b.id) {
      <a
        class="tarjeta fila"
        [routerLink]="['/bolsas', b.id]"
        style="text-decoration: none; color: inherit"
      >
        <div>
          <span class="etiqueta">{{ b.estado }}</span>
          <h3>{{ b.nombre }}</h3>
          <small>Vence {{ b.fecha_limite | fechaBogota }}</small>
        </div>
        <div>
          <span class="etiqueta coral">{{ b.mi_estado }}</span>
          <div>
            <strong>{{ b.mi_parte | pesos }}</strong>
          </div>
        </div>
      </a>
    } @empty {
      <p>No participas en ninguna bolsa todavía.</p>
    }
    <div class="grupo-botones">
      <button class="boton secundario" [disabled]="desde() === 0" (click)="pagina(-1)">
        Anterior
      </button>
      <button class="boton secundario" [disabled]="bolsas().length < porPagina" (click)="pagina(1)">
        Siguiente
      </button>
    </div>
  `,
})
export class Bolsas implements OnInit {
  private readonly api = inject(ApiService);
  protected readonly porPagina = POR_PAGINA;
  readonly bolsas = signal<ResumenBolsa[]>([]);
  readonly desde = signal(0);
  readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.cargar();
  }

  pagina(paso: number): void {
    this.desde.set(Math.max(0, this.desde() + paso * POR_PAGINA));
    this.cargar();
  }

  private cargar(): void {
    this.api.bolsas(this.desde(), POR_PAGINA).subscribe({
      next: (l) => this.bolsas.set(l.bolsas),
      error: (e) => this.error.set(mensajeDe(e)),
    });
  }
}

/** Crear bolsa. Sin clave de idempotencia: no se reintenta sola. */
@Component({
  selector: 'app-crear-bolsa',
  imports: [FormsModule],
  template: `
    <section class="tarjeta">
      <span class="etiqueta">Nueva bolsa</span>
      <h1>Crear bolsa</h1>
      <form (ngSubmit)="crear()">
        <label>Nombre <input name="n" [(ngModel)]="nombre" required /></label>
        <label
          >Total en pesos <input name="t" inputmode="numeric" [(ngModel)]="total" required
        /></label>
        <label
          >Participantes (separados por comas, incluyéndote)
          <input name="p" [(ngModel)]="participantes" placeholder="ana, beto, carla" required />
        </label>
        <label>Cuenta objetivo <input name="o" [(ngModel)]="objetivo" required /></label>
        <label
          >Fecha límite (hora de Bogotá)
          <input name="f" type="datetime-local" [(ngModel)]="fecha" required />
        </label>
        <label class="casilla">
          <input name="v" type="checkbox" [(ngModel)]="transferirAlVencer" />
          Al vencer, enviar lo de quienes pagaron (si no, se devuelve todo)
        </label>
        <p>La división la hace el servidor: el sobrante lo paga quien crea la bolsa.</p>
        <button class="boton" [disabled]="ocupado()">Crear</button>
      </form>
    </section>
    @if (error()) {
      <div class="alerta">
        <span class="etiqueta">Error</span>
        <p>{{ error() }}</p>
      </div>
    }
  `,
})
export class CrearBolsa {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);

  nombre = '';
  total = '';
  participantes = '';
  objetivo = '';
  fecha = '';
  transferirAlVencer = true;
  readonly ocupado = signal(false);
  readonly error = signal<string | null>(null);

  crear(): void {
    const total = leerMonto(this.total);
    const fecha = fechaBogotaConZona(this.fecha);
    if (total === null) {
      this.error.set('El total debe ser un número entero mayor que cero, sin puntos ni decimales.');
      return;
    }
    if (fecha === null) {
      this.error.set('Escribe la fecha límite completa.');
      return;
    }
    this.ocupado.set(true);
    this.error.set(null);
    this.api
      .crearBolsa({
        nombre: this.nombre.trim(),
        total,
        participantes: this.participantes
          .split(',')
          .map((p) => p.trim())
          .filter((p) => p !== ''),
        cuenta_objetivo: this.objetivo.trim(),
        fecha_limite: fecha,
        transferir_al_vencer: this.transferirAlVencer,
      })
      .subscribe({
        next: (b) => void this.router.navigate(['/bolsas', b.id]),
        error: (e) => {
          this.ocupado.set(false);
          this.error.set(mensajeDe(e));
        },
      });
  }
}
