---
title: "Contribuir - Open Minesweeper"
description: "Cómo contribuir al desarrollo de Open Minesweeper, incluyendo la configuración del entorno, la configuración del código, la documentación y el flujo de solicitud de cambios."
---

# Contribuir

Esta página está dirigida a estudiantes que están comenzando a aprender programación y que solo tienen experiencia de clases escolares de programación. No necesitas entender todo el sitio al principio. Si puedes realizar un pequeño cambio y enviarlo a nosotros, ya estás contribuyendo al código abierto.

## ¿Dónde comenzar?

Las contribuciones más adecuadas para principiantes suelen ser tareas pequeñas, como:

- Corregir errores de ortografía en la documentación
- Añadir una breve explicación
- Mejorar el texto en chino o inglés de una página
- Corregir un problema de estilo simple
- Añadir una captura de pantalla
- Convertir un problema que hayas encontrado en una solicitud de ayuda (Issue)

Al principio, no recomendamos cambiar características complejas como el inicio de sesión, los permisos, la revisión de repeticiones, las clasificaciones o el cálculo de torneos.

## Software a instalar

Recomendamos instalar estas herramientas:

| Software | Objetivo |
| --- | --- |
| Git | Descargar el código y guardar los cambios |
| VS Code | Editar el código y la documentación |
| Python | Ejecutar el backend |
| Node.js | Ejecutar el frontend y la documentación |
| MySQL | Base de datos local |
| Redis | Caché local |

Si solo deseas editar la documentación, normalmente solo necesitas:

- Git
- VS Code
- Node.js

## Descargar el código

Abre una terminal, elige un directorio para el código y ejecuta:

```bash
git clone https://github.com/eee555/saolei_website.git
cd saolei_website
```

Si planeas enviar una solicitud de cambios (Pull Request), recomendamos hacer clic en **Fork** en GitHub primero, y luego clonar tu propio repositorio.

## Editar solo la documentación

El directorio de documentación es:

```text
vitepress_doc
```

Ingresa al directorio:

```bash
cd vitepress_doc
```

Instala las dependencias:

```bash
npm install
```

Inicia el sitio de documentación:

```bash
npm run dev
```

Abre esta dirección en tu navegador:

```text
http://localhost:5173/docs/
```

Después de editar los archivos Markdown, el navegador suele refrescarse automáticamente.

Antes de enviarlo, recomendamos ejecutar:

```bash
npm run build
```

Si el proceso de compilación se realiza correctamente, la documentación probablemente no tenga problemas evidentes.

## Ejecutar el frontend

Si deseas cambiar las páginas del sitio web, entra en el directorio del frontend:

```bash
cd front_end
npm install
npm run dev
```

Abre esta dirección en tu navegador:

```text
http://localhost:8080
```

Si solo modificas estilos o texto normal, puedes conectarte al servidor en línea primero:

```bash
npm run frontend
```

Esto te permite evitar configurar un backend local al principio.

## Ejecutar el backend local

Si deseas modificar APIs, bases de datos, inicio de sesión, subida de repeticiones o características similares, necesitas ejecutar el backend.

Entrar en el directorio del backend:

```bash
cd back_end/saolei
```

Crear un entorno virtual:

```bash
python -m venv .venv
```

Activarlo en Windows:

```bash
.\.venv\Scripts\activate
```

Instala las dependencias:

```bash
pip install -r requirements.txt
```

Después de preparar MySQL y Redis, ejecuta:

```bash
python manage.py makemigrations
python manage.py migrate userprofile
python manage.py migrate
python manage.py runserver --nostatic
```

La dirección del backend es:

```text
http://127.0.0.1:8000
```

::: tip
La configuración del backend local es más propensa a errores que la documentación o la configuración del frontend. Si solo quieres hacer tu primera contribución, empezar con documentación o un cambio pequeño en el frontend es más fácil.
:::

## Comandos comunes de verificación

Documentación:

```bash
cd vitepress_doc
npm run build
```

Frontend:

```bash
cd front_end
npm run lint
```

Backend:

```bash
cd back_end/saolei
python manage.py check
```

Si no estás seguro de qué ejecutar, indica esto en la solicitud de cambios:

```text
I changed documentation and only ran npm run build.
```

## Presentar un problema

Los problemas se utilizan para informar fallos o sugerir mejoras.

Un buen problema puede incluir:

- El problema que has encontrado
- Lo que esperabas que pasara
- Lo que realmente pasó
- Pasos para reproducir el problema
- Capturas de pantalla o mensajes de error

Ejemplo:

```text
Title: The tournament page instructions are not clear enough

Problem:
When I first opened the tournament page, I did not know where to fill in the Arbiter identifier.

Expected:
I hope the documentation or page hint explains where to do it.

Screenshot:
...
```

## Presentar una solicitud de cambios

La solicitud de cambios (PR) se suele abreviar como PR. Se utiliza para enviar tus cambios a los mantenedores del proyecto para su revisión.

Proceso básico:

1. Forka el repositorio.
2. Clona tu propio repositorio.
3. Crea una nueva rama.
4. Edita los archivos.
5. Revisa localmente.
6. Agrega tus cambios.
7. Envía a GitHub.
8. Crea una solicitud de cambios en GitHub.

Comandos comunes:

```bash
git checkout -b docs/fix-guide
git status
git add vitepress_doc/zh/guide/some-file.md
git commit -m "docs: improve guide"
git push origin docs/fix-guide
```

Puedes escribir la descripción del PR así:

```text
## What changed
- Improved the explanation in the tournament documentation

## How to check
- npm run build
```

## Si te piden cambiar algo

Los mantenedores pueden dejar comentarios en el PR y pedirte que cambies algunos detalles. Esto es normal y no significa que hayas hecho un mal trabajo.

Solo necesitas:

1. Continuar editando en la misma rama.
2. Hacer un nuevo commit.
3. Hacer un nuevo push.

El PR original se actualizará automáticamente.

## Cómo hacer preguntas

Cuando hagas una pregunta, intenta incluir:

- Lo que estás haciendo
- El comando que ejecutaste
- El mensaje de error completo
- Tu sistema, por ejemplo Windows 11
- Dónde crees que podría estar el problema

En lugar de:

```text
It does not work. What should I do?
```

Es mejor escribir:

```text
I failed to run npm install on Windows 11.
The directory is vitepress_doc.
The last few lines of the error are ...
I am not sure whether my Node.js version is too old.
```

Esto hace mucho más fácil que otros te ayuden.

## La cosa más importante

Tu primera contribución no necesita ser grande. Corregir un error de ortografía, añadir una frase o escribir un issue claro son contribuciones útiles.

Termina un PR pequeño primero, y ya has entrado en la colaboración en código abierto.
