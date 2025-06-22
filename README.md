# TFG – Automatización para Microempresas

Este proyecto forma parte de un Trabajo de Fin de Grado orientado al desarrollo de una herramienta digital que alivia la carga administrativa de microempresas del sector técnico (electricistas, fontaneros, carpinteros, etc.), 
especialmente en entornos rurales. El sistema automatiza tareas clave como la gestión de mensajes, la generación de presupuestos y facturas, la planificación de citas y la trazabilidad documental.

## Características principales

- Centralización de comunicaciones: integración de correo electrónico y WhatsApp, con análisis automático del contenido.
- Generación de presupuestos y facturas: plantillas editables, trazabilidad por estado y validación automática por OCR.
- Gestión de citas: agenda con cálculo inteligente de huecos disponibles, teniendo en cuenta duración, ubicación y desplazamientos.
- Interfaz web modular: frontend ligero, diseñado para usuarios sin experiencia técnica.
- Ejecución local: sin necesidad de servidores externos, compatible con equipos modestos.

## Tecnologías utilizadas

| Componente    | Tecnología             |
|---------------|------------------------|
| Backend       | Python + Flask         |
| Frontend      | HTML, CSS (Grid/Flex), JavaScript |
| Base de datos | MySQL                  |
| IA local      | Mistral vía Ollama     |
| OCR           | Tesseract + OpenCV     |

## Estructura del proyecto

- `/Scripts`: automatización (OCR, IA, generación de documentos, volcado de mensajes…)
- `/Web`: interfaz HTML y hojas de estilo modulares
- `servidor.py`: núcleo de control y rutas Flask
- `.env.bbdd`: variables de entorno para la conexión segura a MySQL

## Objetivo general

Rediseñar el flujo operativo de estos profesionales mediante una solución accesible, estructurada y automatizada, sin sustituir la intervención del usuario. El sistema propone, pero no decide: toda acción requiere validación manual.

## Estado actual

Proyecto funcional y operativo en entorno local

## Autoría

Adela Cervera  
Trabajo de Fin de Grado – Universitat Politècnica de València  
Grado en Tecnología Digital y Multimedia
