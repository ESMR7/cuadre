import { inject } from '@angular/core';
import { CanActivateFn, Router, Routes, withComponentInputBinding } from '@angular/router';

import { SesionService } from './nucleo/sesion.service';
import { Acceso } from './pantallas/acceso';
import { BolsaDetalle } from './pantallas/bolsa-detalle';
import { Bolsas, CrearBolsa } from './pantallas/bolsas';
import { Cuenta } from './pantallas/cuenta';

const conSesion: CanActivateFn = () =>
  inject(SesionService).autenticado() ? true : inject(Router).createUrlTree(['/acceso']);

export const routes: Routes = [
  { path: 'acceso', component: Acceso },
  { path: 'cuenta', component: Cuenta, canActivate: [conSesion] },
  { path: 'bolsas', component: Bolsas, canActivate: [conSesion] },
  { path: 'bolsas/nueva', component: CrearBolsa, canActivate: [conSesion] },
  { path: 'bolsas/:id', component: BolsaDetalle, canActivate: [conSesion] },
  { path: '', pathMatch: 'full', redirectTo: 'cuenta' },
  { path: '**', redirectTo: 'cuenta' },
];

export const opcionesRouter = withComponentInputBinding();
