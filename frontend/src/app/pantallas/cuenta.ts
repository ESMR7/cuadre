import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { ApiService } from '../nucleo/api.service';
import { AvisoService } from '../nucleo/aviso.service';
import { mensajeDe } from '../nucleo/errores';
import { FechaBogotaPipe, PesosPipe, leerMonto } from '../nucleo/formato';
import { IdempotenciaService } from '../nucleo/idempotencia.service';
import { Movimiento } from '../nucleo/tipos';

const POR_PAGINA = 20;

/** Saldo, historial paginado, cargar saldo y transferir. */
@Component({
  selector: 'app-cuenta',
  imports: [FormsModule, RouterLink, PesosPipe, FechaBogotaPipe],
  template: `
    <header class="cabecera">
      <div>
        <span class="etiqueta">Mi cuenta</span>
        <h1>Hola, {{ cuenta() ?? '…' }}</h1>
      </div>
    </header>

    @if (aviso.pendientes().length > 0) {
      <div class="alerta">
        <span class="etiqueta">Bolsas que esperan tu acción</span>
        @for (b of aviso.pendientes(); track b.id) {
          <p>
            <a [routerLink]="['/bolsas', b.id]">{{ b.nombre }}</a
            >:
            {{
              b.mi_estado === 'pendiente' ? 'falta tu aporte de ' : 'debes confirmar tu parte de '
            }}
            {{ b.mi_parte | pesos }} (vence {{ b.fecha_limite | fechaBogota }}).
          </p>
        }
      </div>
    }

    <section class="tarjeta destacada">
      <span class="etiqueta">Saldo disponible</span>
      <div class="saldo">{{ saldo() | pesos }}</div>
    </section>

    @if (error()) {
      <div class="alerta">
        <span class="etiqueta">Error</span>
        <p>{{ error() }}</p>
      </div>
    }
    @if (exito()) {
      <p class="exito">{{ exito() }}</p>
    }

    <div class="columnas">
      <section class="tarjeta formulario">
        <span class="etiqueta">Cargar saldo</span>
        <h2>Agregar dinero</h2>
        <form (ngSubmit)="cargar()">
          <label
            >Monto en pesos
            <input
              name="mc"
              inputmode="numeric"
              placeholder="100000"
              [(ngModel)]="montoCarga"
              (ngModelChange)="cambio('cargar')"
            />
          </label>
          <button class="boton" [disabled]="ocupado()">
            {{ idem.pendiente('cargar') ? 'Reintentar carga' : 'Cargar' }}
          </button>
        </form>
      </section>
      <section class="tarjeta formulario">
        <span class="etiqueta">Transferir</span>
        <h2>Enviar a otra cuenta</h2>
        <form (ngSubmit)="transferir()">
          <label
            >Destino
            <input
              name="d"
              placeholder="nombre de usuario"
              [(ngModel)]="destino"
              (ngModelChange)="cambio('transferir')"
            />
          </label>
          <label
            >Monto en pesos
            <input
              name="mt"
              inputmode="numeric"
              placeholder="20000"
              [(ngModel)]="montoTransferencia"
              (ngModelChange)="cambio('transferir')"
            />
          </label>
          <button class="boton" [disabled]="ocupado()">
            {{ idem.pendiente('transferir') ? 'Reintentar transferencia' : 'Transferir' }}
          </button>
        </form>
      </section>
    </div>

    <section class="seccion">
      <h2>Historial</h2>
      <div class="lista">
        @for (m of movimientos(); track $index) {
          <div class="tarjeta renglon">
            <div class="renglon-texto">
              <span class="etiqueta">{{ m.tipo.replaceAll('_', ' ') }}</span>
              <span class="renglon-titulo">{{ m.contrapartida }}</span>
              <small>{{ m.creado_en | fechaBogota }}</small>
            </div>
            <strong class="monto" [class.negativo]="m.monto < 0">{{ m.monto | pesos }}</strong>
          </div>
        } @empty {
          <p class="vacio">Sin movimientos en esta página.</p>
        }
      </div>
      <div class="paginacion">
        <button class="boton secundario pequeno" [disabled]="desde() === 0" (click)="pagina(-1)">
          ← Anterior
        </button>
        <button
          class="boton secundario pequeno"
          [disabled]="movimientos().length < porPagina"
          (click)="pagina(1)"
        >
          Siguiente →
        </button>
      </div>
    </section>
  `,
})
export class Cuenta implements OnInit {
  private readonly api = inject(ApiService);
  protected readonly idem = inject(IdempotenciaService);
  protected readonly aviso = inject(AvisoService);
  protected readonly porPagina = POR_PAGINA;

  montoCarga = '';
  destino = '';
  montoTransferencia = '';
  readonly cuenta = signal<string | null>(null);
  readonly saldo = signal<number | null>(null);
  readonly movimientos = signal<Movimiento[]>([]);
  readonly desde = signal(0);
  readonly ocupado = signal(false);
  readonly error = signal<string | null>(null);
  readonly exito = signal<string | null>(null);

  ngOnInit(): void {
    this.refrescar();
  }

  cambio(intencion: string): void {
    this.idem.cambioFormulario(intencion);
  }

  pagina(paso: number): void {
    this.desde.set(Math.max(0, this.desde() + paso * POR_PAGINA));
    this.cargarHistorial();
  }

  cargar(): void {
    const monto = leerMonto(this.montoCarga);
    if (monto === null) {
      this.error.set('El monto debe ser un número entero mayor que cero, sin puntos ni decimales.');
      return;
    }
    const clave = this.idem.claveDe('cargar');
    this.ejecutar('cargar', this.api.cargar(monto, clave), () => (this.montoCarga = ''));
  }

  transferir(): void {
    const monto = leerMonto(this.montoTransferencia);
    if (monto === null) {
      this.error.set('El monto debe ser un número entero mayor que cero, sin puntos ni decimales.');
      return;
    }
    const clave = this.idem.claveDe('transferir');
    this.ejecutar('transferir', this.api.transferir(this.destino.trim(), monto, clave), () => {
      this.destino = '';
      this.montoTransferencia = '';
    });
  }

  private ejecutar(
    intencion: string,
    peticion: ReturnType<ApiService['cargar']>,
    limpiar: () => void,
  ): void {
    this.ocupado.set(true);
    this.error.set(null);
    this.exito.set(null);
    peticion.subscribe({
      next: () => {
        this.idem.exito(intencion);
        this.ocupado.set(false);
        limpiar();
        this.exito.set('Operación realizada.');
        this.desde.set(0);
        this.refrescar();
      },
      error: (e: HttpErrorResponse) => {
        this.idem.fallo(intencion, e.status);
        this.ocupado.set(false);
        this.error.set(mensajeDe(e));
      },
    });
  }

  private refrescar(): void {
    this.api.cuenta().subscribe({
      next: (c) => {
        this.cuenta.set(c.cuenta);
        this.saldo.set(c.saldo);
      },
      error: (e) => this.error.set(mensajeDe(e)),
    });
    this.cargarHistorial();
  }

  private cargarHistorial(): void {
    this.api.movimientos(this.desde(), POR_PAGINA).subscribe({
      next: (h) => this.movimientos.set(h.movimientos),
      error: (e) => this.error.set(mensajeDe(e)),
    });
  }
}
