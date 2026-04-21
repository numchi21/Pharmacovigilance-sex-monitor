"""
pharmawatch
===========
Plataforma Python de farmacovigilancia con perspectiva de sexo.

Detecta señales de riesgo diferencial en medicamentos comparando
patrones de efectos adversos entre mujeres y hombres a partir de
datos públicos del sistema FDA FAERS.

Modules
-------
loader
    Carga y validación de datos via openFDA API.
analyzer
    Detección de señales PRR y ROR estratificadas por sexo.
reference_finder
    Búsqueda de fármacos similares via RxNorm API.
exceptions
    Excepciones personalizadas del paquete.
visualizer
    Visualizaciones matplotlib de resultados.
main
    Pipeline de ejecución interactivo.
"""

__version__ = "0.1.0"
__author__ = "Tu Nombre"
__license__ = "MIT"
