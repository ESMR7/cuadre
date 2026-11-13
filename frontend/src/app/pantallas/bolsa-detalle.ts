import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, input, signal } from '@angular/core';

import { ApiService } from '../nucleo/api.service';
import { AvisoService } from '../nucleo/aviso.service';
import { mensajeDe } from '../nucleo/errores';
import { FechaBogotaPipe, PesosPipe } from '../nucleo/formato';
import { IdempotenciaService } from '../nucleo/idempotencia.service';
import { Bolsa } from '../nucleo/tipos';

/**
 * Detalle de una bolsa. Los botones solo se muestran cuando tienen sentido;
 * el backend decide de todos modos. Antes de aportar o confirmar se vuelve a
 * consultar la bolsa y, si la meta o mi parte cambiaron, se avisa y no se envía.
 */
@Component({
  selector: 'app-bolsa-detalle',
  imports: [PesosPipe, FechaBogotaPipe],
  template: `
    @if (bolsa(); as b) {
      <section class="tarjeta">
        <span class="etiqueta">{{ b.estado }}</span>
        <h1>{{ b.nombre }}</h1>
        <dl>
          <dt>Creador</dt>
          <dd>{{ b.creador }}</dd>
          <dt>Cuenta objetivo</dt>
          <dd>{{ b.cuenta_objetivo }}</dd>
          <dt>Total original</dt>
          <dd>{{ b.total | pesos }}</dd>
          <dt>Fecha límite</dt>
          <dd>{{ b.fecha_limite | fechaBogota }}</dd>
          <dt>Al vencer</dt>
          <dd>
            {{ b.transferir_al_vencer ? 'Se envía lo de quienes pagaron' : 'Se devuelve todo' }}
          </dd>
        </dl>
      </section>

      <div class="columnas">
        <section class="tarjeta">
          <span class="etiqueta">Totales</span>
          <dl>
            <dt>Meta</dt>
            <dd>{{ b.meta | pesos }}</dd>
            <dt>Aportado</dt>
            <dd>{{ b.aportado | pesos }}</dd>
            <dt>Transferido</dt>
            <dd>{{ b.transferido | pesos }}</dd>
            <dt>Participantes</dt>
            <dd>{{ b.participantes.total }}</dd>
            <dt>Pagados</dt>
            <dd>{{ b.participantes.pagados }}</dd>
            <dt>Pendientes</dt>
            <dd>{{ b.participantes.pendientes }}</dd>
            <dt>Por confirmar</dt>
            <dd>{{ b.participantes.por_confirmar }}</dd>
            <dt>Retirados</dt>
            <dd>{{ b.participantes.retirados }}</dd>
          </dl>
        </section>
        <section class="tarjeta">
          <span class="etiqueta">Mi participación</span>
          <div class="saldo">{{ b.mi_participacion.parte | pesos }}</div>
          <p>
            Estado: <strong>{{ b.mi_participacion.estado }}</strong>
          </p>
        </section>
      </div>

      @if (cambioTerminos()) {
        <div class="alerta">
          <span class="etiqueta">Los términos cambiaron</span>
          <p>{{ cambioTerminos() }} Revisa y pulsa de nuevo si estás de acuerdo.</p>
        </div>
      }
      @if (error()) {
        <div class="alerta">
          <span class="etiqueta">Error</span>
          <p>{{ error() }}</p>
        </div>
      }
      @if (exito()) {
        <p class="exito">{{ exito() }}</p>
      }

      <div class="grupo-botones">
        @if (puedeAportar()) {
          <button class="boton" [disabled]="ocupado()" (click)="aportar()">
            {{ idem.pendiente(intencion('aportar')) ? 'Reintentar aporte' : 'Aportar ' }}
            {{ idem.pendiente(intencion('aportar')) ? '' : (b.mi_participacion.parte | pesos) }}
          </button>
        }
        @if (puedeConfirmar()) {
          <button class="boton" [disabled]="ocupado()" (click)="confirmar()">Confirmar</button>
        }
        @if (puedeRetirarse()) {
          <button class="boton secundario" [disabled]="ocupado()" (click)="retirarse()">
            {{ idem.pendiente(intencion('retirarse')) ? 'Reintentar retiro' : 'Retirarme' }}
          </button>
        }
        @if (puedeCancelar()) {
          <button class="boton peligro" [disabled]="ocupado()" (click)="cancelar()">
            Cancelar bolsa
          </button>
        }
      </div>
    } @else if (error()) {
      <div class="alerta">
        <span class="etiqueta">Error</span>
        <p>{{ error() }}</p>
      </div>
    } @else {
      <p>Cargando…</p>
    }
  `,
})
export class BolsaDetalle implements OnInit {
  readonly id = input.required<string>();

  private readonly api = inject(ApiService);
  private readonly aviso = inject(AvisoService);
  protected readonly idem = inject(IdempotenciaService);

  readonly bolsa = signal<Bolsa | null>(null);
  readonly ocupado = signal(false);
  readonly error = signal<string | null>(null);
  readonly exito = signal<string | null>(null);
  readonly cambioTerminos = signal<string | null>(null);
  readonly usuario = signal<string | null>(null);

  private readonly vigente = computed(() => {
    const b = this.bolsa();
    return b !== null && (b.estado === 'abierta' || b.estado === 'cancelada');
  });
  readonly puedeAportar = computed(
    () =>
      this.bolsa()?.estado === 'abierta' && this.bolsa()?.mi_participacion.estado === 'pendiente',
  );
  readonly puedeConfirmar = computed(
    () => this.vigente() && this.bolsa()?.mi_participacion.estado === 'por_confirmar',
  );
  readonly puedeRetirarse = computed(
    () => this.vigente() && this.bolsa()?.mi_participacion.estado !== 'retirado',
  );
  readonly puedeCancelar = computed(
    () => this.bolsa()?.estado === 'abierta' && this.bolsa()?.creador === this.usuario(),
  );

  ngOnInit(): void {
    this.api
      .cuenta()
      .subscribe({ next: (c) => this.usuario.set(c.cuenta), error: () => undefined });
    this.refrescar();
  }

  intencion(accion: string): string {
    return `${accion}:${this.id()}`;
  }

  aportar(): void {
    this.conTerminosVigentes(() => {
      const intencion = this.intencion('aportar');
      this.conClave(
        intencion,
        this.api.aportar(this.id(), this.idem.claveDe(intencion)),
        'Aporte realizado.',
      );
    });
  }

  retirarse(): void {
    const intencion = this.intencion('retirarse');
    this.conClave(
      intencion,
      this.api.retirarse(this.id(), this.idem.claveDe(intencion)),
      'Te retiraste de la bolsa.',
    );
  }

  confirmar(): void {
    this.conTerminosVigentes(() =>
      this.sinClave(this.api.confirmar(this.id()), 'Confirmaste los términos.'),
    );
  }

  cancelar(): void {
    this.sinClave(this.api.cancelar(this.id()), 'Bolsa cancelada.');
  }

  /** Consulta la bolsa; si la meta o mi parte cambiaron, avisa y no sigue. */
  private conTerminosVigentes(seguir: () => void): void {
    const antes = this.bolsa();
    this.inicio();
    this.api.bolsa(this.id()).subscribe({
      next: (ahora) => {
        this.bolsa.set(ahora);
        const cambios: string[] = [];
        if (antes && antes.meta !== ahora.meta) {
          cambios.push(`La meta pasó de ${fmt(antes.meta)} a ${fmt(ahora.meta)}.`);
        }
        if (antes && antes.mi_participacion.parte !== ahora.mi_participacion.parte) {
          cambios.push(
            `Tu parte pasó de ${fmt(antes.mi_participacion.parte)} a ${fmt(ahora.mi_participacion.parte)}.`,
          );
        }
        if (cambios.length > 0) {
          this.ocupado.set(false);
          this.cambioTerminos.set(cambios.join(' '));
          return;
        }
        seguir();
      },
      error: (e) => this.fallo(e),
    });
  }

  private conClave(
    intencion: string,
    peticion: ReturnType<ApiService['retirarse']>,
    texto: string,
  ): void {
    this.inicio();
    peticion.subscribe({
      next: () => {
        this.idem.exito(intencion);
        this.terminar(texto);
      },
      error: (e: HttpErrorResponse) => {
        this.idem.fallo(intencion, e.status);
        this.fallo(e);
      },
    });
  }

  private sinClave(peticion: ReturnType<ApiService['confirmar']>, texto: string): void {
    this.inicio();
    peticion.subscribe({ next: () => this.terminar(texto), error: (e) => this.fallo(e) });
  }

  private inicio(): void {
    this.ocupado.set(true);
    this.error.set(null);
    this.exito.set(null);
    this.cambioTerminos.set(null);
  }

  private terminar(texto: string): void {
    this.ocupado.set(false);
    this.exito.set(texto);
    this.aviso.consultar();
    this.refrescar();
  }

  private fallo(e: unknown): void {
    this.ocupado.set(false);
    this.error.set(mensajeDe(e));
  }

  private refrescar(): void {
    this.api.bolsa(this.id()).subscribe({
      next: (b) => this.bolsa.set(b),
      error: (e) => this.error.set(mensajeDe(e)),
    });
  }
}

const fmt = (monto: number) => new PesosPipe().transform(monto);
