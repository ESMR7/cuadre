import { HttpErrorResponse, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

import { environment } from '../../environments/environment';
import { codigoDe } from './errores';
import { SesionService } from './sesion.service';

// Las únicas peticiones sin token: registro y login. Comparación exacta de
// método y ruta; POST /sesiones/renovar y DELETE /sesiones sí llevan token.
const PUBLICAS = new Set(['POST /usuarios', 'POST /sesiones']);

export function esPublica(req: HttpRequest<unknown>): boolean {
  const ruta = new URL(req.url, environment.apiUrl).pathname;
  return PUBLICAS.has(`${req.method.toUpperCase()} ${ruta}`);
}

/** Agrega `Authorization: Bearer <token>` a cada petición autenticada (SPEC 9.5). */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const sesion = inject(SesionService);
  const router = inject(Router);
  const token = sesion.token();
  const conToken =
    token && !esPublica(req)
      ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
      : req;
  return next(conToken).pipe(
    catchError((error: HttpErrorResponse) => {
      if (!esPublica(req) && codigoDe(error) === 'no_autenticado') {
        sesion.cerrar();
        void router.navigate(['/acceso']);
      }
      return throwError(() => error);
    }),
  );
};
