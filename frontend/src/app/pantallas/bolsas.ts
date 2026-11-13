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
    <header class="cabecera">
      <div>
        <span class="etiqueta">Cobros en grupo</span>
        <h1>Mis bolsas</h1>
      </div>
      <a class="boton" routerLink="/bolsas/nueva">+ Crear bolsa</a>
    </header>
    @if (error()) {
      <div class="alerta">
        <span class="etiqueta">Error</span>
        <p>{{ error() }}</p>
      </div>
    }
    <div class="lista">
      @for (b of bolsas(); track b.id) {
        <a class="tarjeta enlace renglon" [routerLink]="['/bolsas', b.id]">
          <div class="renglon-texto">
            <span
              ><span class="chip" [attr.data-estado]="b.estado">{{ b.estado }}</span></span
            >
            <h3 class="renglon-titulo">{{ b.nombre }}</h3>
            <small>Vence {{ b.fecha_limite | fechaBogota }}</small>
          </div>
          <div class="renglon-lado">
            <span class="chip" [attr.data-estado]="b.mi_estado">{{
              b.mi_estado.replaceAll('_', ' ')
            }}</span>
            <strong class="monto neutro">{{ b.mi_parte | pesos }}</strong>
          </div>
        </a>
      } @empty {
        <p class="vacio">No participas en ninguna bolsa todavía.</p>
      }
    </div>
    <div class="paginacion">
      <button class="boton secundario pequeno" [disabled]="desde() === 0" (click)="pagina(-1)">
        ← Anterior
      </button>
      <button
        class="boton secundario pequeno"
        [disabled]="bolsas().length < porPagina"
        (click)="pagina(1)"
      >
        Siguiente →
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
    <div class="estrecho">
      <header class="cabecera">
        <div>
          <span class="etiqueta">Nueva bolsa</span>
          <h1>Crear bolsa</h1>
          <p>Define el total, quiénes participan y a qué cuenta va el dinero al completarse.</p>
        </div>
      </header>
      @if (error()) {
        <div class="alerta">
          <span class="etiqueta">Error</span>
          <p>{{ error() }}</p>
        </div>
      }
      <section class="tarjeta">
        <form (ngSubmit)="crear()">
          <label
            >Nombre <input name="n" [(ngModel)]="nombre" placeholder="Cena del viernes" required
          /></label>
          <label
            >Total en pesos
            <input name="t" inputmode="numeric" [(ngModel)]="total" placeholder="120000" required
          /></label>
          <label
            >Participantes (separados por comas, incluyéndote)
            <input name="p" [(ngModel)]="participantes" placeholder="ana, beto, carla" required />
          </label>
          <div class="columnas">
            <label
              >Cuenta objetivo
              <input name="o" [(ngModel)]="objetivo" placeholder="nombre de usuario" required />
            </label>
            <label
              >Fecha límite (hora de Bogotá)
              <input name="f" type="datetime-local" [(ngModel)]="fecha" required />
            </label>
          </div>
          <label class="casilla">
            <input name="v" type="checkbox" [(ngModel)]="transferirAlVencer" />
            Al vencer, enviar lo de quienes pagaron (si no, se devuelve todo)
          </label>
          <p class="nota">
            La división la hace el servidor: el sobrante lo paga quien crea la bolsa.
          </p>
          <button class="boton" [disabled]="ocupado()">Crear bolsa</button>
        </form>
      </section>
    </div>
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
