import { Pipe, PipeTransform } from '@angular/core';

// El navegador no calcula dinero: solo formatea enteros que vienen de la API
// y valida lo que escribe el usuario (SPEC 9.5).

const MILES = new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0, useGrouping: true });

const FECHA = new Intl.DateTimeFormat('es-CO', {
  timeZone: 'America/Bogota',
  dateStyle: 'medium',
  timeStyle: 'short',
});

/** 100000 → "$100.000"; -20000 → "-$20.000". */
export function formatearPesos(monto: number): string {
  const signo = monto < 0 ? '-' : '';
  return `${signo}$${MILES.format(Math.abs(monto))}`;
}

/** Lee un monto escrito por el usuario: solo dígitos, entero positivo seguro. */
export function leerMonto(texto: string): number | null {
  const limpio = texto.trim();
  if (!/^[1-9]\d*$/.test(limpio)) {
    return null;
  }
  const monto = Number(limpio);
  return Number.isSafeInteger(monto) ? monto : null;
}

/**
 * Convierte el valor de un <input type="datetime-local"> (hora de Bogotá) en
 * ISO 8601 con zona. Colombia no tiene horario de verano: el desfase es -05:00.
 */
export function fechaBogotaConZona(local: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(local)) {
    return null;
  }
  return `${local}:00-05:00`;
}

@Pipe({ name: 'pesos' })
export class PesosPipe implements PipeTransform {
  transform(monto: number | null | undefined): string {
    return monto === null || monto === undefined ? '—' : formatearPesos(monto);
  }
}

@Pipe({ name: 'fechaBogota' })
export class FechaBogotaPipe implements PipeTransform {
  transform(iso: string | null | undefined): string {
    return iso ? FECHA.format(new Date(iso)) : '—';
  }
}
